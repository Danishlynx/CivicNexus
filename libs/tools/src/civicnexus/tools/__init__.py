"""Data-plane access for CivicNexus services.

The case store is the ONLY writer of case state; everything else observes via
events. Transition legality, human-only actions, and the approvals guard are
enforced here — an agent cannot reach around them without bypassing the store,
which the gateway's IAM scoping prevents (§6.1).
"""

from civicnexus.tools.agent_client import (
    check_grounding,
    extract_text,
    query_json,
    query_json_with_events,
    sum_usage,
)
from civicnexus.tools.armor import (
    ArmorClient,
    ArmorVerdict,
    blocking_filters_for,
)
from civicnexus.tools.breaker import CircuitBreaker, loop_signature
from civicnexus.tools.case_store import (
    ApprovalRequiredError,
    CaseStore,
    HumanActionRequiredError,
    IllegalTransitionError,
    TransitionError,
    validate_transition,
)
from civicnexus.tools.events import EventPublisher
from civicnexus.tools.incidents import IncidentStore

__all__ = [
    "ApprovalRequiredError",
    "ArmorClient",
    "ArmorVerdict",
    "CaseStore",
    "CircuitBreaker",
    "EventPublisher",
    "HumanActionRequiredError",
    "IllegalTransitionError",
    "IncidentStore",
    "TransitionError",
    "blocking_filters_for",
    "check_grounding",
    "extract_text",
    "loop_signature",
    "query_json",
    "query_json_with_events",
    "sum_usage",
    "validate_transition",
]
