"""Case wakeup timers: Cloud Tasks → Pub/Sub → timer.fired (§3.1, §5).

A "recheck in N days" wakeup is a real Cloud Tasks task whose schedule_time
honors CLOCK_MULTIPLIER (§10: the warp changes WHEN a real timer fires,
never WHAT fires). The task's HTTP target is Pub/Sub's own REST publish
endpoint for the timer.fired topic, authenticated as sa-timers via OAuth —
deliberately NOT a run.app URL (B-007: this project's Cloud Run URLs are
unroutable at Google's edge) and NOT env-sensitive (ADR-005 §2: the
endpoint is constructed explicitly; nothing here reads GOOGLE_CLOUD_*
routing vars).
"""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from civicnexus.clock import clock_multiplier, warped_delta
from civicnexus.contracts import Actor, EventEnvelope, EventType, Timer
from civicnexus.otel import get_logger

_log = get_logger("timers")


def schedule_case_wakeup(
    *,
    case_id: str,
    days: float,
    reason: str,
    traceparent: str,
    project_id: str,
    location: str,
    queue: str,
    invoker_sa_email: str,
    tasks_client: Any | None = None,
) -> Timer:
    """Create the §4 Timer and its real Cloud Tasks wakeup; returns the Timer.

    The caller persists the Timer on the case (CaseStore.add_timer) — kept
    separate so a store write failure never leaves an untracked live task.
    """
    if tasks_client is None:
        from google.cloud import tasks_v2

        tasks_client = tasks_v2.CloudTasksClient()

    fires_at = datetime.now(UTC) + warped_delta(days)
    timer = Timer(timer_id=f"timer-{uuid.uuid4().hex[:12]}", fires_at=fires_at, reason=reason)

    envelope = EventEnvelope(
        type=EventType.TIMER_FIRED,
        case_id=case_id,
        actor=Actor(agent_id="timers", agent_version="0.1.0"),
        traceparent=traceparent,
        payload={
            "timer_id": timer.timer_id,
            "reason": reason,
            "scheduled_days": days,
            "clock_multiplier": clock_multiplier(),
        },
    )
    publish_body = {
        "messages": [
            {
                "data": base64.b64encode(envelope.model_dump_json().encode("utf-8")).decode(
                    "ascii"
                ),
                "attributes": {
                    "event_type": EventType.TIMER_FIRED.value,
                    "case_id": case_id,
                    "traceparent": traceparent,
                },
            }
        ]
    }
    task: dict[str, Any] = {
        "http_request": {
            "http_method": 1,  # POST
            "url": (
                f"https://pubsub.googleapis.com/v1/projects/{project_id}"
                f"/topics/{EventType.TIMER_FIRED.value}:publish"
            ),
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(publish_body).encode("utf-8"),
            "oauth_token": {"service_account_email": invoker_sa_email},
        },
        "schedule_time": fires_at,
    }
    parent = tasks_client.queue_path(project_id, location, queue)
    created = tasks_client.create_task(request={"parent": parent, "task": task})
    _log.info(
        f"timer scheduled case={case_id}",
        extra={
            "timer_id": timer.timer_id,
            "fires_at": fires_at.isoformat(),
            "clock_multiplier": clock_multiplier(),
            "task_name": created.name,
        },
    )
    return timer
