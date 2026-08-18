"""Pydantic models that are the single source of truth for every CivicNexus schema.

ARCHITECTURE.md §5 (event envelope) and §4 (domain model + case state machine)
define these shapes; code never invents fields that are not specified there.
"""

from civicnexus.contracts.case import (
    ALLOWED_TRANSITIONS,
    Applicant,
    Budget,
    Case,
    CaseState,
    Timer,
    can_transition,
    is_human_only,
)
from civicnexus.contracts.determinations import Citation, Determination, DeterminationOutcome
from civicnexus.contracts.events import Actor, EventEnvelope, EventType
from civicnexus.contracts.intake import Application
from civicnexus.contracts.review import ReviewFinding

__all__ = [
    "ALLOWED_TRANSITIONS",
    "Actor",
    "Applicant",
    "Application",
    "Budget",
    "Case",
    "CaseState",
    "Citation",
    "Determination",
    "DeterminationOutcome",
    "EventEnvelope",
    "EventType",
    "ReviewFinding",
    "Timer",
    "can_transition",
    "is_human_only",
]
