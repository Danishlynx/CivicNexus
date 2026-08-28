"""Simulated-inbox watcher — the long-running background consumer (§6.2).

Two feeders, one queue, one consumer:

- ``--watch-gmail``: polls a REAL mailbox over IMAP for new application
  emails (subject containing "permit application", case-insensitive) and
  queues each one into Firestore ``inbox/``. Receiving is the only
  direction — the system never sends mail (fixture rules). Credentials come
  from env (``INBOX_EMAIL`` + ``INBOX_APP_PASSWORD``, a Gmail app password)
  and are never stored. Fetches use BODY.PEEK and a message is marked seen
  ONLY after it is durably queued, so a crash never loses an application
  (2026-08-28 audit).
- The clerk console's "New application" form queues into the same ``inbox/``.
- The consumer loop claims NEW submissions and drives the PROVEN pipeline —
  the same chain every phase gate ran (scripts/run_case.py): intake agent
  parses the raw text -> case created RECEIVED -> TRIAGED -> IN_REVIEW ->
  engine review -> §7.3 verify (retry once on failure) -> determination ->
  PENDING_HUMAN. Incomplete applications honestly land
  INCOMPLETE_AWAITING_APPLICANT instead.

Resilience (2026-08-28 audit): the loop survives transient IMAP/Firestore
errors (log + backoff, never die); startup requeues claims stranded by a
crashed prior run; an interrupt during a drive marks the submission FAILED
with the partially created case id before exiting. SINGLE consumer per
project — the designed demo shape.

BILLED: each processed application makes engine calls (intake + review).
``--max-cases`` (default 3) bounds a run's spend so a flood of matching
emails cannot drive unbounded engine calls.

Usage:
  uv run python scripts/inbox_watcher.py --consume --i-accept-billing
  uv run python scripts/inbox_watcher.py --consume --watch-gmail --i-accept-billing
  uv run python scripts/inbox_watcher.py --once path.txt --i-accept-billing
"""

import argparse
import email
import email.header
import imaplib
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from typing import Any

from civicnexus.contracts import (
    Actor,
    Applicant,
    Application,
    Case,
    CaseState,
    EventType,
    ReviewFinding,
)
from civicnexus.contracts.permit_types import load_permit_types
from civicnexus.tools import CaseStore, EventPublisher, InboxStore, query_json
from civicnexus.verifier import verify_finding

STATE_FILE = Path(".deploy/caseflow_agent.json")
CORPUS_DIR = Path("data/corpus")
PERMIT_TYPES = Path("config/permit_types.yaml")
AGENT_VERSION = "0.1.0"
SUBJECT_MARKER = "permit application"
QUEUE_POLL_S = 5.0
GMAIL_POLL_S = 15.0
ERROR_BACKOFF_S = 20.0
MAX_EMAIL_BODY_CHARS = 20_000


def _traceparent() -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def _log(message: str) -> None:
    print(f"inbox_watcher: {message}", flush=True)


# --------------------------------------------------------------------------
# The pipeline (mirrors scripts/run_case.py stage for stage)
# --------------------------------------------------------------------------


def drive_application(
    raw_application: str, *, store: CaseStore, remote: Any, created: list[str] | None = None
) -> str:
    """Drive one raw application through intake -> review -> PENDING_HUMAN.

    Returns the case id; appends it to ``created`` the moment the case
    exists, so a caller can attribute a partial case on failure. Mirrors
    run_case.py (the proven chain) so the demo path and the gate-proof path
    cannot drift apart.
    """
    traceparent = _traceparent()
    case_id = f"case-{secrets.token_hex(6)}"

    _log("intake agent parsing the application…")
    intake_msg = json.dumps(
        {
            "task": "intake",
            "application": f"<<<APPLICATION>>>\n{raw_application}\n<<<END APPLICATION>>>",
        }
    )
    application = Application.model_validate(
        query_json(remote, intake_msg, user_prefix="inbox-watcher")
    )
    _log(
        f"intake parsed applicant={application.applicant_name!r} "
        f"type={application.permit_type} complete={application.complete}"
    )

    store.create_case(
        Case(
            case_id=case_id,
            permit_type=application.permit_type,
            applicant=Applicant(name=application.applicant_name, email=application.applicant_email),
            trace_id=traceparent.split("-")[1],
        ),
        traceparent=traceparent,
    )
    if created is not None:
        created.append(case_id)
    _log(f"case {case_id} opened (RECEIVED)")
    store.transition(
        case_id,
        CaseState.TRIAGED,
        EventType.CASE_TRIAGED,
        traceparent=traceparent,
        payload={"missing_items": application.missing_items},
    )
    if not application.complete:
        store.transition(
            case_id,
            CaseState.INCOMPLETE_AWAITING_APPLICANT,
            EventType.APPLICANT_MESSAGE,
            traceparent=traceparent,
            payload={"missing_items": application.missing_items},
        )
        _log(f"case {case_id} incomplete - awaiting applicant ({application.missing_items})")
        return case_id

    store.transition(
        case_id,
        CaseState.IN_REVIEW,
        EventType.REVIEW_REQUESTED,
        traceparent=traceparent,
        payload={"capabilities": ["zoning"]},
    )
    _log(f"case {case_id} in fleet review - the zoning specialist is reading the code…")
    review_msg = json.dumps({"task": "review", "application": application.model_dump()})
    finding = ReviewFinding.model_validate(
        query_json(remote, review_msg, user_prefix="inbox-watcher")
    )

    permit_types = load_permit_types(PERMIT_TYPES)
    permit_cfg = permit_types.get(application.permit_type)
    allowed = permit_cfg.allowed_outcomes if permit_cfg else []
    report = verify_finding(
        finding,
        application=application.model_dump(),
        permit_allowed_outcomes=allowed,
        corpus_dir=CORPUS_DIR,
    )
    if not report.passed:
        _log(f"verifier failed first pass: {report.critique} - one retry with the critique")
        store.transition(
            case_id,
            CaseState.VERIFICATION_FAILED,
            EventType.VERIFICATION_FAILED,
            traceparent=traceparent,
            payload={"failures": report.failures},
        )
        store.transition(
            case_id,
            CaseState.IN_REVIEW,
            EventType.REVIEW_REQUESTED,
            traceparent=traceparent,
            payload={"retry": True},
        )
        retry_msg = json.dumps(
            {
                "task": "review",
                "application": application.model_dump(),
                "verifier_critique": report.critique or "; ".join(report.failures),
            }
        )
        finding = ReviewFinding.model_validate(
            query_json(remote, retry_msg, user_prefix="inbox-watcher")
        )
        report = verify_finding(
            finding,
            application=application.model_dump(),
            permit_allowed_outcomes=allowed,
            corpus_dir=CORPUS_DIR,
        )
    _log(f"verifier {'PASSED' if report.passed else 'failed twice (clerk sees the report)'}")

    determination = finding.to_determination(
        agent_id="zoning",
        agent_version=AGENT_VERSION,
        trace_id=traceparent.split("-")[1],
        verifier_report=report.as_payload(),
    )
    store.add_determination(case_id, determination, traceparent=traceparent)
    store.transition(
        case_id,
        CaseState.PENDING_HUMAN,
        EventType.ACTION_PENDING_APPROVAL,
        traceparent=traceparent,
        payload={"determinations": 1},
    )
    if "CANARY-" in json.dumps(finding.model_dump()):
        _log("WARNING - a canary string surfaced in the finding (leak signal)")
    _log(
        f"case {case_id} at the HUMAN GATE - outcome={finding.outcome.value} "
        f"citations={[c.chunk_id for c in finding.citations]}"
    )
    return case_id


# --------------------------------------------------------------------------
# Gmail feeder (IMAP; PEEK fetches, seen only after durable queueing)
# --------------------------------------------------------------------------


def _decode_header(value: str) -> str:
    parts = email.header.decode_header(value)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                out.append(part.decode(enc or "utf-8", errors="replace"))
            except LookupError:  # unknown codec name in the header
                out.append(part.decode("latin-1", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def _decode_bytes(payload: bytes, charset: str | None) -> str:
    try:
        return payload.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return payload.decode("latin-1", errors="replace")


def _plain_body(message: email.message.Message) -> str:
    """Best-effort text body: text/plain, then de-tagged text/html, then repr."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    return _decode_bytes(payload, part.get_content_charset())
        for part in message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    html = _decode_bytes(payload, part.get_content_charset())
                    return re.sub(r"<[^>]+>", " ", html)
        return ""
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        return _decode_bytes(payload, message.get_content_charset())
    return str(message.get_payload())


def email_to_raw_application(message: email.message.Message) -> str:
    """Reshape a real email into the fixture format intake already parses."""
    sender = _decode_header(message.get("From", ""))
    subject = _decode_header(message.get("Subject", ""))
    body = _plain_body(message).strip()[:MAX_EMAIL_BODY_CHARS]
    return f"From: {sender}\nTo: permits@civicnexus-demo.test\nSubject: {subject}\n\n{body}\n"


def poll_gmail_once(inbox: InboxStore) -> int:
    """Queue UNSEEN matching emails; mark seen ONLY after a durable submit.

    Non-matching mail is never touched (PEEK fetches leave flags alone), and
    a submit failure leaves the message unseen for the next poll.
    """
    address = os.environ["INBOX_EMAIL"]
    password = os.environ["INBOX_APP_PASSWORD"]
    queued = 0
    with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
        imap.login(address, password)
        imap.select("INBOX")
        status, data = imap.search(None, "UNSEEN")
        if status != "OK" or not data or data[0] is None:
            _log(f"gmail search returned {status}; will retry next poll")
            return 0
        for uid in data[0].split():
            status, header_data = imap.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
            if status != "OK" or not header_data or not isinstance(header_data[0], tuple):
                continue
            subject_blob = header_data[0][1].decode("utf-8", errors="replace")
            if SUBJECT_MARKER not in subject_blob.lower():
                continue  # not an application; flags untouched, mail unread
            status, fetched = imap.fetch(uid, "(BODY.PEEK[])")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                continue
            message = email.message_from_bytes(fetched[0][1])
            subject = _decode_header(message.get("Subject", ""))
            raw = email_to_raw_application(message)
            inbox.submit(raw, source="gmail", submitted_by=address)
            # Durably queued - ONLY NOW consume the message.
            imap.store(uid, "+FLAGS", "\\Seen")
            queued += 1
            _log(f"email queued: {subject!r}")
    return queued


# --------------------------------------------------------------------------
# Consumer loop
# --------------------------------------------------------------------------


def _connect() -> tuple[CaseStore, InboxStore, Any]:
    project = os.environ.get("PROJECT_ID")
    if not project:
        raise SystemExit("inbox_watcher: PROJECT_ID env var is required")
    if not STATE_FILE.exists():
        raise SystemExit(f"inbox_watcher: {STATE_FILE} missing - deploy caseflow first")
    deploy_state = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))

    import vertexai
    from google.cloud import firestore

    client = vertexai.Client(project=project, location=deploy_state["region"])
    remote = client.agent_engines.get(name=deploy_state["resource_name"])
    db = firestore.Client(project=project)
    store = CaseStore(
        db,
        EventPublisher(project),
        Actor(agent_id="inbox_watcher", agent_version=AGENT_VERSION),
    )
    return store, InboxStore(db), remote


def _process_one(store: CaseStore, inbox: InboxStore, remote: Any) -> bool:
    """Claim and drive at most one submission; True if one was processed."""
    submission = inbox.next_new()
    if not submission:
        return False
    sid = submission["submission_id"]
    inbox.claim(sid)
    _log(f"processing {sid} (source={submission['source']})")
    created: list[str] = []
    try:
        case_id = drive_application(submission["raw"], store=store, remote=remote, created=created)
        inbox.finish(sid, case_id=case_id)
        return True
    except BaseException as exc:
        # Everything - including KeyboardInterrupt - releases the claim
        # honestly before propagating or continuing (2026-08-28 audit: a
        # stranded PROCESSING row is a silently lost application).
        partial = created[0] if created else ""
        inbox.fail(sid, reason=f"{type(exc).__name__}: {exc}", case_id=partial)
        suffix = f" (partial case {partial})" if partial else ""
        _log(f"FAILED {sid}: {type(exc).__name__}: {exc}{suffix}")
        if not isinstance(exc, Exception):
            raise  # KeyboardInterrupt/SystemExit still stop the watcher
        return True


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consume", action="store_true", help="consume the inbox/ queue")
    parser.add_argument("--watch-gmail", action="store_true", help="also poll Gmail via IMAP")
    parser.add_argument("--once", metavar="FILE", help="drive one application file and exit")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=3,
        help="stop after driving this many cases (bounds billed spend; default 3)",
    )
    parser.add_argument(
        "--i-accept-billing",
        action="store_true",
        help="required: each application drives billed engine calls (spend rule)",
    )
    args = parser.parse_args()

    if not (args.consume or args.once):
        parser.error("nothing to do: pass --consume (and optionally --watch-gmail) or --once")
    if not args.i_accept_billing:
        parser.error("refusing to run billed engine calls without --i-accept-billing (spend rule)")
    if args.watch_gmail and not (
        os.environ.get("INBOX_EMAIL") and os.environ.get("INBOX_APP_PASSWORD")
    ):
        parser.error("--watch-gmail needs INBOX_EMAIL and INBOX_APP_PASSWORD in the environment")

    store, inbox, remote = _connect()

    if args.once:
        raw = Path(args.once).read_text(encoding="utf-8")
        case_id = drive_application(raw, store=store, remote=remote)
        _log(f"done - case {case_id}")
        return 0

    requeued = inbox.requeue_stale()
    if requeued:
        _log(f"recovered {len(requeued)} stale claim(s) from a prior run: {requeued}")

    _log(
        f"consuming the simulated inbox (max {args.max_cases} case(s) this run)"
        + (" + polling Gmail" if args.watch_gmail else "")
        + " - Ctrl+C to stop"
    )
    driven = 0
    last_gmail_poll = 0.0
    while True:
        try:
            if args.watch_gmail and time.monotonic() - last_gmail_poll >= GMAIL_POLL_S:
                last_gmail_poll = time.monotonic()
                poll_gmail_once(inbox)
            if _process_one(store, inbox, remote):
                driven += 1
                if driven >= args.max_cases:
                    _log(f"max-cases reached ({args.max_cases}) - stopping (spend bound)")
                    return 0
            time.sleep(QUEUE_POLL_S)
        except KeyboardInterrupt:
            _log("stopped")
            return 0
        except Exception as exc:
            # A transient IMAP/Firestore blip must not kill the demo's
            # background consumer - log, back off, keep going.
            _log(f"transient error ({type(exc).__name__}: {exc}) - retrying in {ERROR_BACKOFF_S}s")
            time.sleep(ERROR_BACKOFF_S)


if __name__ == "__main__":
    raise SystemExit(main())
