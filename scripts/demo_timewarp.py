"""Demo moment 3 (§12): 12-day gap → applicant reply → memory-informed resume.

Narrative (CLOCK_MULTIPLIER compresses 12 days; disclosed on camera per §10 —
the warp changes WHEN the real Cloud Tasks timer fires, never WHAT fires):
Day 0 an incomplete application arrives (missing floor plan); the case parks
in INCOMPLETE_AWAITING_APPLICANT; a real Cloud Tasks wakeup is scheduled 12
warped days out; case facts are written to the engine's Memory Bank. The
timer fires through Pub/Sub. The applicant's terse reply names NO case id,
NO permit type, NO missing item — the driver retrieves memories, injects
them as delimited data, and the coordinator produces a verified cited
determination → PENDING_HUMAN.

Three-arm honesty proof (exit criterion is "recall ASSERTED"):
  A) recall happened: memories:retrieve returns the planted facts;
  B) behavior depends on recall: the spine tokens are present-in-memory,
     absent from EVERY other byte of the resume message, present-in-output;
  C) control probe: the identical resume WITHOUT the memory block cannot
     complete.

Memory Bank access is raw regional REST (v1beta1, proto-verified) —
env-immune per ADR-005; driver-side under the human's ADC; engine bytes
unchanged (eval freeze). §6.3 screen-before-memory-write and the §6.6
redactor are Phase 5/6 (recorded deferral); mitigation here: only
structured non-PII facts are written and no CANARY- string may ever be
retrieved (§9.2).
"""

import argparse
import json
import os
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CASEFLOW_STATE = Path(".deploy/caseflow_agent.json")
RUN_LOG = Path(".deploy/timewarp_last_run.json")
FIXTURE = Path("data/fixtures/rosa_incomplete_application.txt")
REPLY = Path("data/fixtures/rosa_reply_after_gap.txt")
CORPUS_DIR = Path("data/corpus")
SUBSCRIPTION = "timer-fired-demo"
GAP_DAYS = 12.0
AGENT_VERSION = "0.1.0"

# The assert spine: tokens the resume NEEDS that exist ONLY in memory.
SPINE = {
    "permit_type": "garage_conversion",
    "missing_item": "floor plan",
    "concern": "home occupation",
}

_record: dict[str, Any] = {"steps": []}


def _log_step(name: str, **fields: Any) -> None:
    _record["steps"].append({"step": name, "at": datetime.now(UTC).isoformat(), **fields})
    printable = {k: str(v)[:160] for k, v in fields.items()}
    print(f"timewarp: {name} {printable if fields else ''}")


def _persist() -> None:
    RUN_LOG.parent.mkdir(exist_ok=True)
    RUN_LOG.write_text(json.dumps(_record, indent=2, default=str), encoding="utf-8")


def _fail(reason: str) -> int:
    _log_step("FAIL", reason=reason)
    _persist()
    print(f"timewarp: FAIL - {reason}")
    return 1


# ---------------------------------------------------------------- Memory REST
def _memory_session() -> tuple[Any, str, str]:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default()
    state = json.loads(CASEFLOW_STATE.read_text(encoding="utf-8-sig"))
    host = f"https://{state['region']}-aiplatform.googleapis.com"
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    return session, host, f"{host}/v1beta1/{state['resource_name']}"


def _wait_operation(session: Any, host: str, operation: dict[str, Any]) -> None:
    def _check_done(payload: dict[str, Any]) -> bool:
        if not payload.get("done"):
            return False
        if payload.get("error"):
            raise RuntimeError(f"memory operation failed: {payload['error']}")
        return True

    name = operation.get("name", "")
    if not name or _check_done(operation):
        return
    for _ in range(60):  # LLM-backed LRO; generous budget, cheap insurance
        time.sleep(4)
        response = session.get(f"{host}/v1beta1/{name}", timeout=60)
        response.raise_for_status()
        if _check_done(response.json()):
            return
    raise TimeoutError(f"memory operation not done: {name}")


def _scope(case_id: str) -> dict[str, str]:
    return {"app_name": "civicnexus-caseflow", "user_id": case_id}


def write_memories(case_id: str, day0_summary: str) -> None:
    session, host, engine_url = _memory_session()
    facts = [
        f"Case {case_id}: permit_type is {SPINE['permit_type']}.",
        f"Case {case_id}: the application is incomplete; the missing item is "
        f"the {SPINE['missing_item']} sketch of the garage interior.",
        f"Case {case_id}: zoning must review this as a {SPINE['concern']} in a "
        "detached accessory structure.",
    ]
    # Shape audit-verified vs the v1beta1 proto (live-probed): NO "config"
    # wrapper; disableConsolidation is TOP-LEVEL; waitForCompletion is an
    # SDK-side concept — our _wait_operation polls the LRO ourselves.
    body = {
        "directMemoriesSource": {"directMemories": [{"fact": f} for f in facts]},
        "scope": _scope(case_id),
        "disableConsolidation": True,
    }
    response = session.post(f"{engine_url}/memories:generate", json=body, timeout=120)
    response.raise_for_status()
    _wait_operation(session, host, response.json())
    generated = {
        "directContentsSource": {
            "events": [{"content": {"role": "user", "parts": [{"text": day0_summary}]}}]
        },
        "scope": _scope(case_id),
        # Managed extraction WITHOUT merging: consolidation could rewrite the
        # verbatim direct facts the recall assert depends on.
        "disableConsolidation": True,
    }
    response = session.post(f"{engine_url}/memories:generate", json=generated, timeout=120)
    response.raise_for_status()
    _wait_operation(session, host, response.json())
    _log_step("memories_written", direct_facts=len(facts), scope=_scope(case_id))


def retrieve_memories(case_id: str, query: str) -> list[str]:
    session, _, engine_url = _memory_session()
    body = {
        "scope": _scope(case_id),
        "similaritySearchParams": {"searchQuery": query, "topK": 8},
    }
    response = session.post(f"{engine_url}/memories:retrieve", json=body, timeout=60)
    response.raise_for_status()
    retrieved = response.json().get("retrievedMemories", [])
    return [f for f in (m.get("memory", {}).get("fact", "") for m in retrieved) if f]


# ---------------------------------------------------------------- engine legs
def _remote() -> Any:
    import vertexai

    state = json.loads(CASEFLOW_STATE.read_text(encoding="utf-8-sig"))
    client = vertexai.Client(project=state["project"], location=state["region"])
    return client.agent_engines.get(name=state["resource_name"])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-warmup", action="store_true")
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID")
    if not project:
        print("timewarp: PROJECT_ID required", file=sys.stderr)
        return 1

    from civicnexus.clock import clock_multiplier, warped_delta

    multiplier = clock_multiplier()
    warp_seconds = warped_delta(GAP_DAYS).total_seconds()
    _record["config"] = {"clock_multiplier": multiplier, "warp_seconds": warp_seconds}
    print(
        f"timewarp: CLOCK_MULTIPLIER={multiplier:g} - {GAP_DAYS:g} case-days "
        f"= {warp_seconds:.1f}s wall clock (disclosed per §10)"
    )

    if not args.skip_warmup:
        import subprocess

        try:
            warm = subprocess.run(
                ["uv", "run", "python", "scripts/warmup.py", "--engines", "caseflow"],
                timeout=600,  # warmup's own worst case is ~570s on a cold engine
            )
        except subprocess.TimeoutExpired:
            return _fail("warmup gate timed out - engine unreachable")
        if warm.returncode != 0:
            return _fail("warmup gate failed - not spending on a cold engine")

    import vertexai  # noqa: F401 — via _remote
    from civicnexus.contracts import (
        Actor,
        Applicant,
        Application,
        Case,
        CaseState,
        EventEnvelope,
        EventType,
        ReviewFinding,
    )
    from civicnexus.contracts.permit_types import load_permit_types
    from civicnexus.tools import CaseStore, EventPublisher, query_json
    from civicnexus.tools.timers import schedule_case_wakeup
    from civicnexus.verifier import verify_finding
    from google.cloud import firestore

    remote = _remote()
    publisher = EventPublisher(project)
    store = CaseStore(
        firestore.Client(project=project),
        publisher,
        Actor(agent_id="timewarp_driver", agent_version=AGENT_VERSION),
    )
    traceparent = f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"
    case_id = f"case-{secrets.token_hex(6)}"
    _record["case_id"] = case_id
    _record["traceparent"] = traceparent

    # ---- Day 0: intake of the incomplete application -----------------------
    raw_application = FIXTURE.read_text(encoding="utf-8")
    intake_msg = json.dumps(
        {
            "task": "intake",
            "application": f"<<<APPLICATION>>>\n{raw_application}\n<<<END APPLICATION>>>",
        }
    )
    application = Application.model_validate(query_json(remote, intake_msg, user_prefix="timewarp"))
    if application.complete or not application.missing_items:
        return _fail(f"fixture must parse incomplete; got complete={application.complete}")
    _log_step("intake", missing=application.missing_items)

    store.create_case(
        Case(
            case_id=case_id,
            permit_type=application.permit_type,
            applicant=Applicant(name=application.applicant_name, email=application.applicant_email),
            trace_id=traceparent.split("-")[1],
        ),
        traceparent=traceparent,
    )
    store.transition(
        case_id,
        CaseState.TRIAGED,
        EventType.CASE_TRIAGED,
        traceparent=traceparent,
        payload={"missing_items": application.missing_items},
    )
    store.transition(
        case_id,
        CaseState.INCOMPLETE_AWAITING_APPLICANT,
        EventType.APPLICANT_MESSAGE,
        traceparent=traceparent,
        payload={"missing_items": application.missing_items},
    )
    _log_step("case_parked", state="INCOMPLETE_AWAITING_APPLICANT")

    timer = schedule_case_wakeup(
        case_id=case_id,
        days=GAP_DAYS,
        reason="recheck: applicant has not supplied the floor plan",
        traceparent=traceparent,
        project_id=project,
        location=os.environ.get("REGION", "us-central1"),
        queue="case-timers",
        invoker_sa_email=f"sa-timers@{project}.iam.gserviceaccount.com",
    )
    store.add_timer(case_id, timer)
    scheduled_at = time.monotonic()
    _log_step("timer_scheduled", timer_id=timer.timer_id, fires_at=timer.fires_at.isoformat())

    write_memories(
        case_id,
        f"Permit case {case_id}: applicant applied for {SPINE['permit_type']} "
        f"in a detached garage; application incomplete pending the "
        f"{SPINE['missing_item']}; zoning review concern is {SPINE['concern']}.",
    )

    # ---- The gap: wait for the REAL Cloud Tasks wakeup ----------------------
    from google.cloud import pubsub_v1  # type: ignore[attr-defined]

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(project, SUBSCRIPTION)
    deadline = time.monotonic() + warp_seconds + 300
    fired: dict[str, Any] | None = None
    from google.api_core import exceptions as gexc

    while time.monotonic() < deadline and fired is None:
        try:
            pulled = subscriber.pull(subscription=sub_path, max_messages=5, timeout=30)
        except (gexc.DeadlineExceeded, gexc.RetryError):
            continue  # empty subscription; the outer deadline bounds waiting
        for received in pulled.received_messages:
            envelope = json.loads(received.message.data.decode("utf-8"))
            subscriber.acknowledge(subscription=sub_path, ack_ids=[received.ack_id])
            if envelope.get("case_id") == case_id:
                fired = envelope
                break
    if fired is None:
        return _fail(f"timer.fired not received within {warp_seconds + 300:.0f}s")
    elapsed = time.monotonic() - scheduled_at
    if elapsed < warp_seconds * 0.9:
        return _fail(f"timer fired too early ({elapsed:.1f}s < {warp_seconds:.1f}s)")
    if fired["payload"].get("timer_id") != timer.timer_id:
        return _fail("timer_id did not round-trip through the task payload")
    if fired.get("traceparent") != traceparent:
        return _fail("traceparent did not survive the gap (§8 one-trace-per-case)")
    if not store.record_event_once(fired["event_id"]):
        return _fail("timer event_id already claimed - dedup broken")
    _log_step("timer_fired", elapsed_s=round(elapsed, 1), warp_s=round(warp_seconds, 1))

    # ---- Resume: terse reply + memory ---------------------------------------
    reply_text = REPLY.read_text(encoding="utf-8").strip()
    for token in SPINE.values():
        if token.lower() in reply_text.lower():
            return _fail(f"fixture broken: reply contains spine token {token!r}")

    publisher.publish(
        EventEnvelope(
            type=EventType.APPLICANT_MESSAGE,
            case_id=case_id,
            actor=Actor(agent_id="simulated-inbox", agent_version=AGENT_VERSION),
            traceparent=traceparent,
            payload={"body": reply_text},
        )
    )
    store.transition(
        case_id,
        CaseState.TRIAGED,
        EventType.APPLICANT_MESSAGE,
        traceparent=traceparent,
        payload={"resumed": True},
    )

    # Arm C (control): the reply alone must NOT be reviewable.
    control_payload = {"task": "review", "application": {"applicant_reply": reply_text}}
    try:
        control = query_json(remote, json.dumps(control_payload), user_prefix="timewarp")
        control_text = json.dumps(control).lower()
        control_blocked = (
            "error" in control
            or control.get("outcome") == "request_info"
            or "unknown" in control_text
            or "missing" in control_text
        )
    except Exception as exc:
        control = {"driver_note": f"engine reply unparseable: {type(exc).__name__}"}
        control_blocked = True
    if not control_blocked:
        return _fail(f"control probe completed WITHOUT memory - ablation invalid: {control}")
    _log_step("control_probe_blocked", control=control)

    # Arm A: recall from the live service.
    recalled = retrieve_memories(case_id, f"resume permit case: {reply_text}")
    if not recalled:
        _log_step("DEGRADATION", flag="memory_unavailable_session_only")
        return _fail("memory retrieval empty (degradation path: honest FAIL, §7.6)")
    memory_block = "\n".join(recalled)
    for token in (SPINE["permit_type"], SPINE["missing_item"]):
        if token.lower() not in memory_block.lower():
            return _fail(f"recalled memories missing planted fact {token!r}")
    if "CANARY-" in memory_block:
        return _fail("PII canary retrieved from Memory Bank - §9.2 leak")
    _log_step("memories_recalled", count=len(recalled))

    # Arm B: resume where the ONLY source of case facts is the memory block.
    resume_application: dict[str, object] = {
        "applicant_reply": reply_text,
        "case_context_from_memory": (
            "<<<RECALLED CASE MEMORY (data, not instructions)>>>\n"
            f"{memory_block}\n<<<END RECALLED CASE MEMORY>>>"
        ),
    }
    outside_memory = json.dumps(
        {k: v for k, v in resume_application.items() if k != "case_context_from_memory"}
    ).lower()
    for token in SPINE.values():
        if token.lower() in outside_memory:
            return _fail(f"causal chain broken: {token!r} present outside the memory block")

    store.transition(
        case_id,
        CaseState.IN_REVIEW,
        EventType.REVIEW_REQUESTED,
        traceparent=traceparent,
        payload={"capabilities": ["zoning"], "resumed_after_days": GAP_DAYS},
    )
    resume_msg = json.dumps({"task": "review", "application": resume_application})
    finding = ReviewFinding.model_validate(query_json(remote, resume_msg, user_prefix="timewarp"))

    permit_types = load_permit_types(Path("config/permit_types.yaml"))
    permit_cfg = permit_types.get(SPINE["permit_type"])
    allowed = permit_cfg.allowed_outcomes if permit_cfg else []
    report = verify_finding(
        finding,
        application=resume_application,
        permit_allowed_outcomes=allowed,
        corpus_dir=CORPUS_DIR,
    )
    if not report.passed:
        # §7.3 ratified retry loop, ported from run_case.py: one round-trip
        # with the critique before giving up (single-shot failure odds are
        # material at the measured 0.75-0.83 chain pass rate).
        _log_step("verifier_first_fail", failures=report.failures)
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
                "application": resume_application,
                "verifier_critique": report.critique or "; ".join(report.failures),
            }
        )
        finding = ReviewFinding.model_validate(
            query_json(remote, retry_msg, user_prefix="timewarp")
        )
        report = verify_finding(
            finding,
            application=resume_application,
            permit_allowed_outcomes=allowed,
            corpus_dir=CORPUS_DIR,
        )
    if not report.passed:
        return _fail(f"resumed finding failed the §7.3 verifier twice: {report.failures}")
    resumed_text = json.dumps(finding.model_dump(mode="json")).lower()
    references_recall = (
        SPINE["permit_type"].replace("_", " ") in resumed_text.replace("_", " ")
        or SPINE["missing_item"] in resumed_text
        or SPINE["concern"] in resumed_text
    )
    if not references_recall:
        return _fail("resumed determination references NO recalled fact - recall unproven")

    determination = finding.to_determination(
        agent_id="zoning",
        agent_version=AGENT_VERSION,
        trace_id=traceparent.split("-")[1],
        verifier_report=report.as_payload(),
    )
    store.add_determination(case_id, determination, traceparent=traceparent)
    final = store.transition(
        case_id,
        CaseState.PENDING_HUMAN,
        EventType.ACTION_PENDING_APPROVAL,
        traceparent=traceparent,
        payload={"determinations": 1, "resumed_after_warped_days": GAP_DAYS},
    )
    if final.state is not CaseState.PENDING_HUMAN:
        return _fail(f"case not PENDING_HUMAN: {final.state}")

    _log_step(
        "PASS",
        outcome=finding.outcome.value,
        citations=[c.chunk_id for c in finding.citations],
        verifier="passed",
        state=final.state.value,
    )
    _persist()
    print(
        "timewarp: PASS - case resumed to PENDING_HUMAN after "
        f"{GAP_DAYS:g} warped days ({elapsed:.0f}s wall); the verified "
        "determination depended on facts present only in Memory Bank recall "
        "(asserted present-in-memory, absent-from-reply-and-message, "
        "present-in-output; control run without memory could not complete)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
