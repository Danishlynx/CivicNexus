"""DLQ replay drill with real Pub/Sub mechanics (ADR-006 D13).

The §11 exit criterion is "a dead-lettered event replays without duplicate side
effects". A drill that hand-fed the same bytes to a function twice would prove
the dedup helper works and nothing else, so this one uses the live path: a real
publish to ``timer.fired``, real repeated nacks on ``timer-fired-drill`` until
Pub/Sub itself forwards the message to ``timer.fired.dlq``, and a real
republish of the ORIGINAL bytes as they came back off the dead-letter topic.

Three things that shaped the design and are easy to get wrong:

  **max_delivery_attempts is approximate.** The subscription asks for 5, and
  Pub/Sub documents that number as a target, not a contract — it may forward
  after more. So nothing here counts to five. The drill nacks until the message
  is *observed* on the DLQ subscription, under one generous overall deadline
  that fails with a named cause; the configured attempt count is read in
  preflight and recorded as evidence, never used as a loop bound. The
  subscription also carries a 10s->60s retry_policy backoff, so the wait is
  minutes rather than seconds even on a healthy path.

  **Dead-lettering only works when the Pub/Sub service agent can subscribe.**
  ``timer-fired-demo`` carried a dead_letter_policy but never had the
  per-subscription ``roles/pubsub.subscriber`` grant to
  ``service-<project#>@gcp-sa-pubsub.iam.gserviceaccount.com``, which made
  ``make dlq-replay`` silently unreachable until the B-010 recovery session on
  2026-08-26 found it. ``timer-fired-drill`` is created with its own grant
  (D13/D17), which is why dead-lettering genuinely happens on this path. The
  preflight asserts the policy is present and points at ``timer.fired.dlq``
  rather than assuming the apply landed.

  **The side effect has to be countable, not merely idempotent.** A ``create``
  would raise on the second write and the drill could never observe a duplicate
  at all. Instead each admitted delivery appends its OWN document under
  ``drill_dlq_replay/<event_id>/side_effects/``, so "how many side effects
  happened" is answered by counting documents. The guard under test is
  ``CaseStore.record_event_once(event_id)`` (§5 dedup): the write happens only
  when it returns True.

Scope, stated plainly on the PASS line: there is no deployed ``timer.fired``
consumer anywhere in CivicNexus. The consumer is the ``consume()`` function in
this file, driven by this driver. What is proven is that a dead-lettered
envelope survives the round trip byte-identically and that the dedup mechanism
admits exactly one of its replays — not that some service in production behaves
that way.

Pub/Sub only: no engine call, no model call, so the run is effectively $0.
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from civicnexus.contracts import Actor, EventEnvelope, EventType
from civicnexus.tools.case_store import CaseStore
from civicnexus.tools.events import EventPublisher

RUN_LOG = Path(".deploy/dlq_replay_last_run.json")

#: Terraform-managed names (ADR-006 D13/D16). The topic id equals the envelope
#: type verbatim, the same invariant libs/tools/events.py relies on.
TOPIC = EventType.TIMER_FIRED.value
DLQ_TOPIC = "timer.fired.dlq"
DRILL_SUBSCRIPTION = "timer-fired-drill"
DLQ_SUBSCRIPTION = "timer-fired-dlq-replay"
DEMO_SUBSCRIPTION = "timer-fired-demo"

#: Exactly the attributes libs/tools/events.py sets on a publish. An allowlist,
#: not a denylist of the CloudPubSubDeadLetter* keys Pub/Sub adds: a replay is
#: supposed to look like the original publish, and any attribute the platform
#: grows later would otherwise ride along and misdescribe the replayed message.
PUBLISHED_ATTRIBUTES = frozenset({"event_type", "case_id", "traceparent"})

#: Where the one defined side effect lands. Drill-scoped by name so nothing in
#: this file can write into cases/, incidents/ or any collection real casework
#: reads.
SIDE_EFFECT_COLLECTION = "drill_dlq_replay"
SIDE_EFFECT_SUBCOLLECTION = "side_effects"

#: D13: the ORIGINAL bytes are republished twice. Two is the smallest number
#: that can expose a duplicate side effect at all, and a larger number would
#: only repeat the same assertion at more Pub/Sub round trips.
REPLAY_COUNT = 2

#: Generous by design, and sized against armor.tf rather than guessed: the drill
#: subscription's retry_policy backs off 10s -> 60s between deliveries, so five
#: attempts alone cost roughly 10+20+40+60+60 = 190s of waiting, and
#: max_delivery_attempts is approximate in the upward direction. A ceiling near
#: that arithmetic would fail honest runs. The bound exists so a broken
#: dead_letter_policy or a missing service-agent grant fails with a named cause
#: instead of hanging — never to time the forwarding.
DEFAULT_DEADLINE_S = 600.0

#: Per-pull wait. Short so the nack loop and the DLQ poll can interleave inside
#: one overall deadline.
_PULL_TIMEOUT_S = 10.0

AGENT_VERSION = "1.0.0"
DRILL_ACTOR_ID = "dlq-replay-drill"

_record: dict[str, Any] = {"steps": []}


class DrillFailure(Exception):
    """An assertion failed; the message becomes the named cause on the FAIL line."""


def _log(name: str, **fields: Any) -> None:
    """Record a step in the evidence file and echo it, ASCII-safe for Windows."""
    _record["steps"].append({"step": name, "at": datetime.now(UTC).isoformat(), **fields})
    printable = {k: str(v)[:140] for k, v in fields.items()}
    print(f"dlq-replay: {name} {printable if fields else ''}")


def _persist() -> None:
    """Write evidence BEFORE any parsing or assertion can raise."""
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text(json.dumps(_record, indent=2, default=str), encoding="utf-8", newline="\n")


def _digest(data: bytes) -> str:
    """Short sha256 so raw payload bytes can be compared in the evidence file.

    The evidence file is JSON and the envelope is UTF-8 JSON itself; recording a
    digest alongside the decoded text makes a byte-level difference visible even
    where a reader would gloss over the text as "the same message".
    """
    return hashlib.sha256(data).hexdigest()


def mint_traceparent() -> str:
    """A fresh W3C traceparent for this drill run (§8 one-trace-per-case).

    Minted here rather than inherited: the whole point of the byte-equality
    assertion is that THIS value survives publish -> dead-letter -> replay, so
    it must be unique to the run or a stale match could pass for continuity.
    """
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def build_envelope(case_id: str, traceparent: str) -> EventEnvelope:
    """The synthetic timer.fired envelope this drill dead-letters.

    A real §5 envelope, not a hand-rolled blob: it has to survive Pub/Sub, the
    dead-letter hop and ``model_validate_json`` on the way back, and a shape
    that only this drill can parse would prove nothing about the event contract.
    The payload is marked as drill-scoped so anyone reading the raw message on
    the DLQ can tell what it is without opening this file.
    """
    return EventEnvelope(
        type=EventType.TIMER_FIRED,
        case_id=case_id,
        actor=Actor(agent_id=DRILL_ACTOR_ID, agent_version=AGENT_VERSION),
        traceparent=traceparent,
        payload={
            "drill": "dlq-replay",
            "adr": "ADR-006 D13",
            "reason": "synthetic dead-letter replay drill; no real case exists",
            "timer_id": f"timer-{uuid4().hex[:12]}",
        },
    )


def preflight(subscriber: Any, project: str) -> dict[str, Any]:
    """Prove the D13 plumbing exists before publishing anything ($0, fail closed).

    Without the dead_letter_policy the nack loop would spin to its deadline and
    report a timeout, which reads like a slow forward rather than absent infra —
    exactly the misdiagnosis B-010 cost a session to. The configured
    max_delivery_attempts is captured as evidence only; see the module docstring
    for why it is never a loop bound.
    """
    drill_path = subscriber.subscription_path(project, DRILL_SUBSCRIPTION)
    dlq_path = subscriber.subscription_path(project, DLQ_SUBSCRIPTION)

    try:
        drill_sub = subscriber.get_subscription(subscription=drill_path)
    except Exception as exc:
        raise DrillFailure(
            f"subscription {DRILL_SUBSCRIPTION} is not readable ({type(exc).__name__}: {exc}); "
            "has the Phase 5 terraform been applied?"
        ) from exc
    try:
        dlq_sub = subscriber.get_subscription(subscription=dlq_path)
    except Exception as exc:
        raise DrillFailure(
            f"subscription {DLQ_SUBSCRIPTION} is not readable ({type(exc).__name__}: {exc}); "
            "has the Phase 5 terraform been applied?"
        ) from exc

    policy = drill_sub.dead_letter_policy
    dead_letter_topic = str(getattr(policy, "dead_letter_topic", "") or "")
    attempts = int(getattr(policy, "max_delivery_attempts", 0) or 0)
    summary: dict[str, Any] = {
        "drill_subscription": str(drill_sub.name),
        "drill_source_topic": str(drill_sub.topic),
        "dead_letter_topic": dead_letter_topic,
        "max_delivery_attempts_configured": attempts,
        "max_delivery_attempts_is_approximate": True,
        "dlq_subscription": str(dlq_sub.name),
        "dlq_subscription_topic": str(dlq_sub.topic),
    }
    _record["preflight"] = summary
    _persist()
    _log(
        "preflight",
        dead_letter_topic=dead_letter_topic or "NONE",
        attempts_configured=attempts,
        dlq_sub_topic=str(dlq_sub.topic),
    )

    if not dead_letter_topic:
        raise DrillFailure(
            f"{DRILL_SUBSCRIPTION} has no dead_letter_policy - nothing would ever be "
            "dead-lettered (D13 subscription not applied)"
        )
    if not dead_letter_topic.endswith(f"/topics/{DLQ_TOPIC}"):
        raise DrillFailure(
            f"{DRILL_SUBSCRIPTION} dead-letters to {dead_letter_topic}, not {DLQ_TOPIC}"
        )
    if not str(dlq_sub.topic).endswith(f"/topics/{DLQ_TOPIC}"):
        raise DrillFailure(
            f"{DLQ_SUBSCRIPTION} is attached to {dlq_sub.topic}, not {DLQ_TOPIC} - it could "
            "never observe the dead-lettered message"
        )
    return summary


def _envelope_event_id(data: bytes) -> str:
    """Read an event_id out of raw message bytes without trusting the shape.

    Foreign traffic on a shared subscription must never crash the drill or,
    worse, be mistaken for ours; anything unparseable simply is not our message.
    """
    try:
        parsed: Any = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("event_id", ""))


def nack_until_dead_lettered(
    subscriber: Any, project: str, event_id: str, *, deadline_s: float
) -> dict[str, Any]:
    """Nack on the drill subscription until the message is observed on the DLQ.

    Interleaved rather than sequential: the DLQ poll runs in the same loop as
    the nacks, because Pub/Sub may forward at any attempt and a drill that
    nacked a fixed number of times first would either under-nack (never
    forwarded) or keep nacking a message that had already moved.

    Foreign messages are left strictly alone — neither acked nor nacked. Acking
    would destroy another run's evidence, and nacking would inflate somebody
    else's delivery count toward THEIR dead-letter threshold.
    """
    drill_path = subscriber.subscription_path(project, DRILL_SUBSCRIPTION)
    dlq_path = subscriber.subscription_path(project, DLQ_SUBSCRIPTION)

    from google.api_core import exceptions as gexc

    nacks = 0
    foreign_seen: set[str] = set()
    started = time.monotonic()
    deadline = started + deadline_s

    while time.monotonic() < deadline:
        try:
            pulled = subscriber.pull(
                subscription=drill_path, max_messages=10, timeout=_PULL_TIMEOUT_S
            )
        except (gexc.DeadlineExceeded, gexc.RetryError):
            pulled = None
        if pulled is not None:
            ours: list[Any] = []
            for received in pulled.received_messages:
                if _envelope_event_id(received.message.data) == event_id:
                    ours.append(received)
                else:
                    foreign_seen.add(str(received.message.message_id))
            if ours:
                # ack_deadline_seconds=0 is the nack: redeliver immediately.
                subscriber.modify_ack_deadline(
                    subscription=drill_path,
                    ack_ids=[received.ack_id for received in ours],
                    ack_deadline_seconds=0,
                )
                nacks += len(ours)
                _record["nacks"] = nacks
                _persist()

        try:
            dlq_pulled = subscriber.pull(
                subscription=dlq_path, max_messages=10, timeout=_PULL_TIMEOUT_S
            )
        except (gexc.DeadlineExceeded, gexc.RetryError):
            continue
        for received in dlq_pulled.received_messages:
            if _envelope_event_id(received.message.data) != event_id:
                # Not ours: leave it outstanding rather than acking somebody
                # else's dead letter out of existence.
                continue
            data: bytes = received.message.data
            attributes = {str(k): str(v) for k, v in dict(received.message.attributes).items()}
            # Ack only OUR dead letter, so repeated drill runs do not pile up on
            # the DLQ and the next run's poll cannot match a stale message.
            subscriber.acknowledge(subscription=dlq_path, ack_ids=[received.ack_id])
            observed: dict[str, Any] = {
                "nacks_before_dead_letter": nacks,
                "elapsed_s": round(time.monotonic() - started, 1),
                "message_id_on_dlq": str(received.message.message_id),
                "attributes": attributes,
                "sha256": _digest(data),
                "bytes": len(data),
                "foreign_messages_left_untouched": sorted(foreign_seen),
            }
            _record["dead_letter"] = observed
            _persist()
            _log(
                "dead-lettered",
                nacks=nacks,
                elapsed_s=observed["elapsed_s"],
                delivery_attempt=attributes.get("CloudPubSubDeadLetterSourceDeliveryCount", "?"),
            )
            return {**observed, "data": data}

    raise DrillFailure(
        f"the message did not appear on {DLQ_SUBSCRIPTION} within {deadline_s:.0f}s after "
        f"{nacks} nack(s) - check the per-subscription roles/pubsub.subscriber grant to the "
        "Pub/Sub service agent on timer-fired-drill (the B-010 failure mode)"
    )


def republish_original(
    publisher: Any, project: str, data: bytes, attributes: dict[str, str]
) -> str:
    """Publish the exact dead-lettered bytes back onto timer.fired.

    The bytes handed in are the ones Pub/Sub returned from the DLQ, not a
    re-serialization of a parsed envelope: a replay that re-encodes its payload
    would quietly launder any difference the round trip introduced, and
    byte-equality end to end is half of what this drill claims.

    Only the three attributes libs/tools/events.py sets are carried forward. The
    ``CloudPubSubDeadLetter*`` attributes Pub/Sub adds are dead-letter metadata,
    not part of the original event, and replaying them would misdescribe the
    message as having been dead-lettered again.
    """
    topic_path = publisher.topic_path(project, TOPIC)
    carried = {k: v for k, v in attributes.items() if k in PUBLISHED_ATTRIBUTES}
    future = publisher.publish(topic_path, data, **carried)
    message_id: str = future.result(timeout=30.0)
    return message_id


def consume(store: CaseStore, db: Any, data: bytes, *, delivery: int) -> dict[str, Any]:
    """The driver-side consumer path: dedup first, then the one side effect.

    This is the whole mechanism under test. ``record_event_once`` claims the
    event_id transactionally; the Firestore write happens ONLY when that claim
    succeeds. Every admitted delivery writes its own document (see the module
    docstring) so a duplicate would be counted rather than swallowed by a
    constraint violation.

    There is no deployed timer.fired consumer in CivicNexus — this function is
    it, and the PASS line says so.
    """
    envelope = EventEnvelope.model_validate_json(data)
    event_id = str(envelope.event_id)
    claimed = store.record_event_once(event_id)
    row: dict[str, Any] = {
        "delivery": delivery,
        "event_id": event_id,
        "traceparent": envelope.traceparent,
        "sha256": _digest(data),
        "claimed": claimed,
        "side_effect_doc": None,
    }
    if claimed:
        doc_id = uuid4().hex
        db.collection(SIDE_EFFECT_COLLECTION).document(event_id).collection(
            SIDE_EFFECT_SUBCOLLECTION
        ).document(doc_id).create(
            {
                "drill": "dlq-replay",
                "adr": "ADR-006 D13",
                "delivery": delivery,
                "case_id": envelope.case_id,
                "traceparent": envelope.traceparent,
                "written_at": datetime.now(UTC),
            }
        )
        row["side_effect_doc"] = (
            f"{SIDE_EFFECT_COLLECTION}/{event_id}/{SIDE_EFFECT_SUBCOLLECTION}/{doc_id}"
        )
    _log(
        "consume", delivery=delivery, claimed=claimed, side_effect=row["side_effect_doc"] or "none"
    )
    return row


def replay_and_consume(
    publisher: Any,
    subscriber: Any,
    store: CaseStore,
    db: Any,
    *,
    project: str,
    data: bytes,
    attributes: dict[str, str],
    event_id: str,
    deadline_s: float,
) -> dict[str, Any]:
    """Republish the original bytes REPLAY_COUNT times and consume each delivery.

    The replays go back through the topic and are pulled off the drill
    subscription again, so the dedup guard is exercised across two genuinely
    separate Pub/Sub deliveries rather than two calls in a loop. Each delivery
    of ours is acked immediately after ``consume()`` returns: leaving one
    outstanding would let it redeliver and add an unplanned delivery to the very
    count this drill asserts on.
    """
    from google.api_core import exceptions as gexc

    drill_path = subscriber.subscription_path(project, DRILL_SUBSCRIPTION)
    published: list[str] = []
    for _ in range(REPLAY_COUNT):
        published.append(republish_original(publisher, project, data, attributes))
    _record["replay_message_ids"] = published
    _persist()
    _log("republished", count=len(published), message_ids=published)

    consumed: list[dict[str, Any]] = []
    deadline = time.monotonic() + deadline_s
    while len(consumed) < REPLAY_COUNT and time.monotonic() < deadline:
        try:
            pulled = subscriber.pull(
                subscription=drill_path, max_messages=10, timeout=_PULL_TIMEOUT_S
            )
        except (gexc.DeadlineExceeded, gexc.RetryError):
            continue
        for received in pulled.received_messages:
            if _envelope_event_id(received.message.data) != event_id:
                continue  # foreign traffic: never acked, never nacked
            row = consume(store, db, received.message.data, delivery=len(consumed) + 1)
            row["replayed_bytes_match_original"] = received.message.data == data
            row["message_id"] = str(received.message.message_id)
            subscriber.acknowledge(subscription=drill_path, ack_ids=[received.ack_id])
            consumed.append(row)
            _record["consumed"] = consumed
            _persist()

    if len(consumed) < REPLAY_COUNT:
        raise DrillFailure(
            f"only {len(consumed)} of {REPLAY_COUNT} replayed deliveries arrived on "
            f"{DRILL_SUBSCRIPTION} within {deadline_s:.0f}s"
        )
    return {"published_message_ids": published, "consumed": consumed}


def count_side_effects(db: Any, event_id: str) -> int:
    """Count the documents the consumer path actually wrote for this event_id.

    Read back from Firestore rather than trusted from the in-process tally: the
    claim is about side effects that happened, and an in-memory counter would
    agree with itself even if a write went somewhere unexpected.
    """
    docs = (
        db.collection(SIDE_EFFECT_COLLECTION)
        .document(event_id)
        .collection(SIDE_EFFECT_SUBCOLLECTION)
        .stream()
    )
    return sum(1 for _ in docs)


def drain_demo_subscription(subscriber: Any, project: str, event_id: str) -> dict[str, Any]:
    """Ack this drill's own copies off timer-fired-demo; touch nothing else.

    ``timer.fired`` also feeds ``timer-fired-demo``, so every publish here leaves
    a copy that demo_timewarp and timer_canary would later pull and discard.
    Cleaning up our own ids keeps those runs from wading through drill traffic.
    Scoped to our event_id and best-effort: a failure here is reported, never
    fatal, because it is housekeeping and not the thing under test.
    """
    from google.api_core import exceptions as gexc

    path = subscriber.subscription_path(project, DEMO_SUBSCRIPTION)
    acked: list[str] = []
    error: str | None = None
    deadline = time.monotonic() + 45.0
    try:
        while time.monotonic() < deadline and len(acked) < REPLAY_COUNT + 1:
            try:
                pulled = subscriber.pull(subscription=path, max_messages=10, timeout=5.0)
            except (gexc.DeadlineExceeded, gexc.RetryError):
                break  # nothing pending; our copies may simply not have landed
            ours = [
                received
                for received in pulled.received_messages
                if _envelope_event_id(received.message.data) == event_id
            ]
            if not ours:
                continue
            subscriber.acknowledge(
                subscription=path, ack_ids=[received.ack_id for received in ours]
            )
            acked.extend(str(received.message.message_id) for received in ours)
    except Exception as exc:  # housekeeping only - reported, never fatal
        error = f"{type(exc).__name__}: {exc}"
    summary: dict[str, Any] = {
        "subscription": DEMO_SUBSCRIPTION,
        "acked_own_copies": acked,
        "error": error,
    }
    _record["demo_drain"] = summary
    _persist()
    _log("demo-drain", acked=len(acked), error=error or "none")
    return summary


def assert_continuity(
    original: bytes, dead_letter: dict[str, Any], replay: dict[str, Any], traceparent: str
) -> dict[str, Any]:
    """Assert byte-equality and traceparent continuity across every hop.

    Checked at three places rather than one, because they fail for different
    reasons: the dead-letter forward (Pub/Sub re-wrapping the payload), the
    republish (a driver that re-serialized instead of replaying), and the
    attribute (trace context riding beside the payload per §8, which is what a
    consumer written against attributes would actually read).
    """
    dlq_data: bytes = dead_letter["data"]
    attributes: dict[str, str] = dead_letter["attributes"]
    mismatches: list[str] = []

    if dlq_data != original:
        mismatches.append("the dead-lettered payload is not byte-identical to what was published")
    if attributes.get("traceparent") != traceparent:
        mismatches.append(
            f"traceparent attribute on the DLQ message is {attributes.get('traceparent')!r}, "
            f"not the minted {traceparent!r}"
        )
    for row in replay["consumed"]:
        if not row["replayed_bytes_match_original"]:
            mismatches.append(
                f"replay delivery {row['delivery']} payload differs from the original"
            )
        if row["traceparent"] != traceparent:
            mismatches.append(
                f"replay delivery {row['delivery']} carries traceparent {row['traceparent']!r}"
            )

    summary: dict[str, Any] = {
        "traceparent": traceparent,
        "published_sha256": _digest(original),
        "dead_letter_sha256": _digest(dlq_data),
        "replay_sha256": sorted({str(row["sha256"]) for row in replay["consumed"]}),
        "mismatches": mismatches,
    }
    _record["continuity"] = summary
    _persist()
    if mismatches:
        raise DrillFailure("; ".join(mismatches))
    return summary


def run_drill(
    publisher: Any,
    subscriber: Any,
    store: CaseStore,
    db: Any,
    *,
    project: str,
    deadline_s: float,
) -> dict[str, Any]:
    """Publish, dead-letter, replay, and assert exactly one side effect."""
    preflight(subscriber, project)

    traceparent = mint_traceparent()
    case_id = f"drill-dlq-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:8]}"
    envelope = build_envelope(case_id, traceparent)
    event_id = str(envelope.event_id)
    original = envelope.model_dump_json().encode("utf-8")

    _record["case_id"] = case_id
    _record["event_id"] = event_id
    _record["traceparent"] = traceparent
    _record["published_sha256"] = _digest(original)
    _record["envelope"] = json.loads(original.decode("utf-8"))
    _persist()

    message_id = EventPublisher(project_id=project).publish(envelope)
    _record["publish_message_id"] = message_id
    _persist()
    _log("published", topic=TOPIC, event_id=event_id, message_id=message_id)

    dead_letter = nack_until_dead_lettered(subscriber, project, event_id, deadline_s=deadline_s)
    replay = replay_and_consume(
        publisher,
        subscriber,
        store,
        db,
        project=project,
        data=dead_letter["data"],
        attributes=dead_letter["attributes"],
        event_id=event_id,
        deadline_s=deadline_s,
    )
    continuity = assert_continuity(original, dead_letter, replay, traceparent)

    claimed = [row for row in replay["consumed"] if row["claimed"]]
    observed = count_side_effects(db, event_id)
    _record["side_effect_count"] = observed
    _record["claimed_deliveries"] = len(claimed)
    _persist()
    _log("side-effects", written=observed, claimed_deliveries=len(claimed), replays=REPLAY_COUNT)

    if observed != 1:
        raise DrillFailure(
            f"{observed} side effect(s) recorded for {REPLAY_COUNT} replays of one event_id - "
            "record_event_once did not deduplicate"
        )
    if len(claimed) != 1:
        raise DrillFailure(
            f"record_event_once admitted {len(claimed)} of {REPLAY_COUNT} replayed deliveries"
        )

    drain_demo_subscription(subscriber, project, event_id)
    return {
        "event_id": event_id,
        "case_id": case_id,
        "nacks": dead_letter["nacks_before_dead_letter"],
        "replays": REPLAY_COUNT,
        "side_effects": observed,
        "continuity": continuity,
    }


def main() -> int:
    """Run the drill and print a PASS/FAIL line scoped to the driver-side path."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deadline",
        type=float,
        default=DEFAULT_DEADLINE_S,
        help=(
            "overall seconds to wait for the dead-letter forward and for each replay batch; "
            "a bound so absent infra fails with a cause, never a delivery-attempt count"
        ),
    )
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID", "").strip()
    if not project:
        print("FAIL: dlq-replay - PROJECT_ID is not set")
        return 1
    _record["project"] = project
    _record["deadline_s"] = args.deadline
    _record["started_at"] = datetime.now(UTC).isoformat()
    _persist()

    try:
        # Pub/Sub clients take no project kwarg - the project rides in every
        # resource path, built here from the validated PROJECT_ID (D2, F8).
        from google.cloud import firestore, pubsub_v1  # type: ignore[attr-defined]

        subscriber: Any = pubsub_v1.SubscriberClient()
        publisher: Any = pubsub_v1.PublisherClient()
        db: Any = firestore.Client(project=project)
        store = CaseStore(
            db,
            EventPublisher(project_id=project),
            Actor(agent_id=DRILL_ACTOR_ID, agent_version=AGENT_VERSION),
        )
    except Exception as exc:
        _record["client_error"] = repr(exc)
        _persist()
        print(f"FAIL: dlq-replay - client construction for {project} failed: {exc}")
        return 1

    try:
        result = run_drill(
            publisher, subscriber, store, db, project=project, deadline_s=args.deadline
        )
    except DrillFailure as exc:
        _record["failure"] = str(exc)
        _record["finished_at"] = datetime.now(UTC).isoformat()
        _persist()
        print(f"FAIL: dlq-replay (driver-side consumer path) - {exc}; evidence {RUN_LOG}")
        return 1
    except Exception as exc:  # fail closed on ANY unexpected error, with the cause
        _record["error"] = repr(exc)
        _record["finished_at"] = datetime.now(UTC).isoformat()
        _persist()
        print(f"FAIL: dlq-replay (driver-side consumer path) - {type(exc).__name__}: {exc}")
        print(f"      evidence {RUN_LOG}")
        return 1

    _record["finished_at"] = datetime.now(UTC).isoformat()
    _persist()
    print(
        f"dlq-replay: event {result['event_id']} dead-lettered after {result['nacks']} nack(s), "
        f"replayed {result['replays']}x from the ORIGINAL bytes, "
        f"{result['side_effects']} side effect recorded"
    )
    print(
        "PASS: dlq-replay (driver-side consumer path - there is no deployed timer.fired "
        "consumer; the consumer is scripts/dlq_replay.py:consume, guarded by "
        f"CaseStore.record_event_once); evidence {RUN_LOG}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
