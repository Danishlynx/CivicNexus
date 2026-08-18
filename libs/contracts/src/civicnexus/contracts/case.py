"""Case state machine vocabulary (ARCHITECTURE.md §4).

Phase 1 adds the Case and Determination models plus transition enforcement;
Phase 0 pins the state vocabulary only, so services and events can reference
states by one shared name from day one.
"""

from enum import StrEnum


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
