"""Incident record for the incident.raised path (ARCHITECTURE.md §3.2, §6.3, §7.2).

Raised when the pipeline blocks screened content (Model Armor verdict, ADR-006
D6) or the circuit breaker opens on a loop signature (§7.2, ADR-006 D12). The
record persists to Firestore ``incidents/`` and rides the ``incident.raised``
event as its payload — never silently dropped (§6.3).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ScreeningPoint(StrEnum):
    """The four §6.3 Model Armor screening points, ADR-006 D1."""

    INBOUND_CONTENT = "inbound_content"
    WORKER_OUTPUT = "worker_output"
    LETTER_DRAFT = "letter_draft"
    MEMORY_WRITE = "memory_write"


class IncidentKind(StrEnum):
    """What raised the incident."""

    ARMOR_SCREENING = "armor_screening"
    CIRCUIT_BREAKER = "circuit_breaker"


class IncidentStatus(StrEnum):
    """Incident lifecycle: opened by the machine, resolved only by a human."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class FilterMatch(BaseModel):
    """One Model Armor filter's verdict, with attribution (ADR-006 D2/D8).

    ``confidence`` is empty for filters that expose no confidence level
    (malicious URIs) and for non-match records kept as evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    filter: str
    match_state: str
    confidence: str = ""


class Incident(BaseModel):
    """One incident, keyed by ``incident_id`` in Firestore ``incidents/``.

    ``cause`` names exactly why the pipeline acted (F7: fail-closed guards log
    their cause) — a blocking filter match, EXECUTION_SKIPPED, an HTTP failure,
    or a breaker loop signature. ``quarantine_uri`` is set only when content
    bytes were moved to the quarantine bucket.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str
    case_id: str
    kind: IncidentKind
    cause: str
    screening_point: ScreeningPoint | None = None
    filter_matches: list[FilterMatch] = Field(default_factory=list)
    quarantine_uri: str = ""
    traceparent: str
    actor: str
    ts: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status: IncidentStatus = IncidentStatus.OPEN

    @model_validator(mode="after")
    def _screening_incidents_name_their_point(self) -> "Incident":
        if self.kind is IncidentKind.ARMOR_SCREENING and self.screening_point is None:
            raise ValueError("armor_screening incidents must name a screening_point")
        return self

    def as_payload(self) -> dict[str, Any]:
        """The incident as an ``incident.raised`` event payload."""
        return self.model_dump(mode="json")
