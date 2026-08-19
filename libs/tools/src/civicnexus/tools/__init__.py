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
from civicnexus.tools.case_store import (
    ApprovalRequiredError,
    CaseStore,
    HumanActionRequiredError,
    IllegalTransitionError,
    TransitionError,
    validate_transition,
)
from civicnexus.tools.events import EventPublisher

__all__ = [
    "ApprovalRequiredError",
    "CaseStore",
    "EventPublisher",
    "HumanActionRequiredError",
    "IllegalTransitionError",
    "TransitionError",
    "check_grounding",
    "extract_text",
    "query_json",
    "query_json_with_events",
    "sum_usage",
    "validate_transition",
]
