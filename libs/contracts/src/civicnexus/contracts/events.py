"""Event envelope and topic types for all inter-component communication.

Every Pub/Sub message and every A2A message carries this envelope
(ARCHITECTURE.md §5). Consumers deduplicate on ``event_id`` before any side
effect; the envelope is versioned via ``schema_version``.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventType(StrEnum):
    """Topic names from ARCHITECTURE.md §5 — one enum member per Pub/Sub topic."""

    CASE_RECEIVED = "case.received"
    CASE_TRIAGED = "case.triaged"
    REVIEW_REQUESTED = "review.requested"
    REVIEW_COMPLETED = "review.completed"
    VERIFICATION_FAILED = "verification.failed"
    APPLICANT_MESSAGE = "applicant.message"
    TIMER_FIRED = "timer.fired"
    ACTION_PENDING_APPROVAL = "action.pending_approval"
    ACTION_APPROVED = "action.approved"
    LETTER_SENT = "letter.sent"
    INCIDENT_RAISED = "incident.raised"
    CASE_CLOSED = "case.closed"


class Actor(BaseModel):
    """The agent (or service) that emitted an event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    agent_version: str


class EventEnvelope(BaseModel):
    """Versioned envelope wrapping every event payload (ARCHITECTURE.md §5).

    ``traceparent`` carries W3C trace context across async hops so one trace
    spans the whole case. Unknown fields are rejected — a malformed or injected
    envelope must fail validation loudly, never be silently narrowed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    schema_version: Literal[1] = 1
    type: EventType
    case_id: str
    ts: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: Actor
    traceparent: str
    payload: dict[str, Any] = Field(default_factory=dict)
