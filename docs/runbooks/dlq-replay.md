# Runbook — DLQ replay drill (ADR-006 D13)

Proves the §11 exit criterion: **a dead-lettered event replays without duplicate
side effects.** Pub/Sub only — no engine call, so effectively $0.

```
PROJECT_ID=civicnexus-hack26 make dlq-replay
```

## What it actually does

1. Publishes a synthetic `EventEnvelope` to `timer.fired` with a fresh
   `event_id` (uuid4) and a minted traceparent.
2. Pulls from `timer-fired-drill` and **nacks until the message is observed on
   the DLQ** via `timer-fired-dlq-replay`.
3. Republishes the **original bytes** twice.
4. Runs the driver-side consumer on each replay. The side effect — a
   drill-scoped Firestore write — executes only when
   `CaseStore.record_event_once(event_id)` returns `True`. That call is the
   idempotency mechanism under test.
5. Asserts the side effect happened **exactly once** across two replays, and
   that the traceparent is byte-equal at all three hops.

## Expect this, and read it carefully

```
dlq-replay: dead-lettered {'nacks': '5', 'elapsed_s': '113.7', 'delivery_attempt': '5'}
dlq-replay: consume {'delivery': '1', 'claimed': 'True',  'side_effect': 'drill_dlq_replay/...'}
dlq-replay: consume {'delivery': '2', 'claimed': 'False', 'side_effect': 'none'}
dlq-replay: side-effects {'written': '1', 'claimed_deliveries': '1', 'replays': '2'}
PASS: dlq-replay (driver-side consumer path - there is no deployed timer.fired
      consumer; the consumer is scripts/dlq_replay.py:consume, guarded by
      CaseStore.record_event_once)
```

The PASS line is deliberately scoped. **There is no deployed `timer.fired`
consumer** — the consumer is the driver itself. Do not quote this as "the
service deduplicated"; it is the driver-side consumer path, and the run says so.

## It takes minutes, not seconds

`timer-fired-drill` carries a retry policy of 10s min / 60s max backoff, so five
delivery attempts cost roughly 10+20+40+60+60 ≈ 190s of backoff before the
message dead-letters. Measured runs: **113–130s to dead-letter.** The overall
deadline is 600s.

`max_delivery_attempts` is **approximate and biased upward** — never write or
expect an exactly-5 loop. The drill nacks until it observes the DLQ, under one
bounded deadline, precisely because the count is not contractual.

## If it fails

| Symptom | Cause | Fix |
|---|---|---|
| Never dead-letters, deadline hit | The Pub/Sub service agent lacks `roles/pubsub.subscriber` on the subscription — Pub/Sub then cannot forward to the DLQ **at all** | Check `gcloud pubsub subscriptions get-iam-policy timer-fired-drill`. This exact grant was missing on `timer-fired-demo` until 2026-08-26 and made dead-lettering silently impossible (B-010) |
| `preflight` fails on dead_letter_policy | `timer-fired-drill` was recreated without its DLQ policy | `terraform apply` (armor.tf owns it) |
| Side effects > 1 | Real idempotency regression — `record_event_once` is not claiming | Do **not** rerun hoping for green; this is the criterion failing |
| Side effects == 0 | The consumer never ran, or claimed nothing | Check the pull leg; a zero here is not a pass |

## Cleanup

The drill drains its own copies off `timer-fired-demo` on the way out and writes
evidence to `.deploy/dlq_replay_last_run.json` before parsing anything, so a
crashed run still leaves a usable record. Firestore side-effect documents live
under `drill_dlq_replay/<event_id>/` and are drill-scoped — they are evidence,
not garbage, and are left in place.
