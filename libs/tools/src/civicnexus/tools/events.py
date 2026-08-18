"""Event publishing (ARCHITECTURE.md §5).

Topic IDs equal the envelope ``type`` strings verbatim (created by Terraform),
so publishing cannot drift from the contract. ``traceparent`` rides as a
message attribute so trace context survives the async hop (§8).
"""

from typing import Any

from civicnexus.contracts import EventEnvelope

_PUBLISH_TIMEOUT_S = 10.0


class EventPublisher:
    """Publishes validated envelopes to their Pub/Sub topic."""

    def __init__(self, project_id: str, client: Any | None = None) -> None:
        if client is None:
            from google.cloud import pubsub_v1  # type: ignore[attr-defined]

            client = pubsub_v1.PublisherClient()
        self._client = client
        self._project_id = project_id

    def publish(self, envelope: EventEnvelope) -> str:
        """Publish one envelope; returns the Pub/Sub message id.

        Blocking with a bounded timeout: an event that cannot be published is
        a failed side effect the caller must see, never a silent drop.
        """
        topic_path = f"projects/{self._project_id}/topics/{envelope.type.value}"
        future = self._client.publish(
            topic_path,
            envelope.model_dump_json().encode("utf-8"),
            event_type=envelope.type.value,
            case_id=envelope.case_id,
            traceparent=envelope.traceparent,
        )
        message_id: str = future.result(timeout=_PUBLISH_TIMEOUT_S)
        return message_id
