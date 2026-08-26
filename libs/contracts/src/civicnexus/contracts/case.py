"""Case domain model and state machine (ARCHITECTURE.md §4).

Every field is transcribed from §4's domain model — nothing invented. Shapes
§4 leaves unspecified (``docs[]``, ``timers[]``) are kept deliberately minimal
and documented; they harden in the phase that owns them (docs at intake in
this phase, timers in Phase 4 durability).

Transition legality lives here so every service shares one truth; *enforcement*
(including the approvals-row guard on ISSUED/DENIED/letter sends) lives in the
case store, which is the only writer.
"""

from datetime import UTC, datetime
from enum import StrEnum

from civicnexus.contracts.determinations import Determination
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class CaseState(StrEnum):
    """Every state a permit case can occupy, verbatim from ARCHITECTURE.md §4."""

    RECEIVED = "RECEIVED"
    TRIAGED = "TRIAGED"
    INCOMPLETE_AWAITING_APPLICANT = "INCOMPLETE_AWAITING_APPLICANT"
    IN_REVIEW = "IN_REVIEW"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    PAUSED_BUDGET = "PAUSED_BUDGET"
    PENDING_HUMAN = "PENDING_HUMAN"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    INFO_REQUESTED = "INFO_REQUESTED"
    ISSUED = "ISSUED"
    QUARANTINED = "QUARANTINED"
    CLOSED = "CLOSED"


#: Legal transitions per the §4 diagram. QUARANTINED's exits (ADR-006 D6, with
#: incident handling): a human either re-admits the case for review or discards
#: it — both human-only via HUMAN_ONLY_SOURCES, enforced by the case store.
ALLOWED_TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    CaseState.RECEIVED: frozenset({CaseState.TRIAGED}),
    CaseState.TRIAGED: frozenset({CaseState.INCOMPLETE_AWAITING_APPLICANT, CaseState.IN_REVIEW}),
    CaseState.INCOMPLETE_AWAITING_APPLICANT: frozenset({CaseState.TRIAGED}),
    CaseState.IN_REVIEW: frozenset(
        {CaseState.VERIFICATION_FAILED, CaseState.PENDING_HUMAN, CaseState.PAUSED_BUDGET}
    ),
    CaseState.VERIFICATION_FAILED: frozenset({CaseState.IN_REVIEW}),
    CaseState.PAUSED_BUDGET: frozenset({CaseState.PENDING_HUMAN}),
    CaseState.PENDING_HUMAN: frozenset(
        {CaseState.APPROVED, CaseState.DENIED, CaseState.INFO_REQUESTED}
    ),
    CaseState.APPROVED: frozenset({CaseState.ISSUED}),
    CaseState.ISSUED: frozenset({CaseState.CLOSED}),
    CaseState.DENIED: frozenset({CaseState.CLOSED}),
    CaseState.INFO_REQUESTED: frozenset({CaseState.INCOMPLETE_AWAITING_APPLICANT}),
    CaseState.QUARANTINED: frozenset({CaseState.IN_REVIEW, CaseState.CLOSED}),
    CaseState.CLOSED: frozenset(),
}

#: Transitions only a named human may perform (§4: "human action only", and
#: quarantine exits are human-only by §4's note).
HUMAN_ONLY_SOURCES: frozenset[CaseState] = frozenset(
    {CaseState.PENDING_HUMAN, CaseState.QUARANTINED}
)


def can_transition(current: CaseState, target: CaseState) -> bool:
    """Return whether §4 permits moving from ``current`` to ``target``.

    Any state except QUARANTINED itself may enter QUARANTINED (Model Armor
    incident path); everything else follows the transition map.
    """
    if target is CaseState.QUARANTINED:
        return current is not CaseState.QUARANTINED
    return target in ALLOWED_TRANSITIONS[current]


def is_human_only(current: CaseState) -> bool:
    """Return whether transitions out of ``current`` require a human actor."""
    return current in HUMAN_ONLY_SOURCES


class Applicant(BaseModel):
    """The permit applicant of record (synthetic data only — fixture rules)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    email: str


class Budget(BaseModel):
    """Per-case spend counters, enforced by the coordinator (§7.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hops_used: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0


class Timer(BaseModel):
    """A scheduled wakeup ("recheck in N days", §3.1). Refined in Phase 4."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timer_id: str
    fires_at: AwareDatetime
    reason: str


class Case(BaseModel):
    """A permit case, verbatim field list from ARCHITECTURE.md §4.

    ``docs`` holds storage URIs of received documents; the structured
    application extracted from them lives in determinations' inputs, not here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    permit_type: str
    applicant: Applicant
    docs: list[str] = Field(default_factory=list)
    state: CaseState = CaseState.RECEIVED
    determinations: list[Determination] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    timers: list[Timer] = Field(default_factory=list)
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str = ""
