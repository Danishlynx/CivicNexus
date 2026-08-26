"""$0 canary for the timer path (RUNBOOK step after applying timers.tf).

Schedules a ~15s dummy wakeup for a synthetic case id and waits for the
timer.fired message — proving queue, sa-timers publish rights (fresh-IAM
propagation), and the subscription end to end BEFORE any paid demo leg.
"""

import json
import os
import sys
import time

from civicnexus.tools.timers import schedule_case_wakeup


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    if not project:
        print("timer_canary: PROJECT_ID required", file=sys.stderr)
        return 1
    os.environ["CLOCK_MULTIPLIER"] = "69120"  # 12 days -> 15s
    case_id = f"canary-{int(time.time())}"
    timer = schedule_case_wakeup(
        case_id=case_id,
        days=12,
        reason="canary",
        traceparent=f"00-{'0' * 32}-{'0' * 16}-01",
        project_id=project,
        location=os.environ.get("REGION", "us-central1"),
        queue="case-timers",
        invoker_sa_email=f"sa-timers@{project}.iam.gserviceaccount.com",
    )
    print(f"timer_canary: scheduled {timer.timer_id}, waiting up to 420s (IAM propagation)...")

    from google.api_core import exceptions as gexc
    from google.cloud import pubsub_v1  # type: ignore[attr-defined]

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(project, "timer-fired-demo")
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        try:
            pulled = subscriber.pull(subscription=sub_path, max_messages=5, timeout=30)
        except (gexc.DeadlineExceeded, gexc.RetryError):
            continue
        for received in pulled.received_messages:
            envelope = json.loads(received.message.data.decode("utf-8"))
            subscriber.acknowledge(subscription=sub_path, ack_ids=[received.ack_id])
            if envelope.get("case_id") == case_id:
                print(f"timer_canary: PASS - fired in {time.monotonic() - (deadline - 420):.0f}s")
                return 0
    print("timer_canary: FAIL - no timer.fired within 420s (IAM propagation or queue issue)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
