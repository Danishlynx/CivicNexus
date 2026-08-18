"""Pydantic models that are the single source of truth for every CivicNexus schema.

ARCHITECTURE.md §5 (event envelope) and §4 (case state machine) define these shapes;
code never invents fields that are not specified there.
"""

from civicnexus.contracts.case import CaseState
from civicnexus.contracts.events import Actor, EventEnvelope, EventType

__all__ = ["Actor", "CaseState", "EventEnvelope", "EventType"]
