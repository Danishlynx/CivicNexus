"""Clerk-action derivation (ADR-007 D5 rule 1; A10 scope ruling).

Buttons are DERIVED from the §4 contract, never hardcoded: the target set for
a state is exactly ``ALLOWED_TRANSITIONS[state]``, the approval-row
requirement is exactly ``target in APPROVAL_REQUIRED_TARGETS``, and whether a
human is contractually required comes from ``is_human_only``. The only
product judgment layered on top is WHICH states the clerk owns — the ratified
A10 ruling: the clerk completes a case from the human gate onward
(PENDING_HUMAN → APPROVED → ISSUED → CLOSED, DENIED → CLOSED, and the
QUARANTINED re-admit/discard). Upstream states belong to the fleet, and the
UI says so instead of rendering dead buttons.
"""

from dataclasses import dataclass

from civicnexus.contracts import (
    ALLOWED_TRANSITIONS,
    APPROVAL_REQUIRED_TARGETS,
    CaseState,
    EventType,
)

#: A10: the clerk owns the case from the human gate onward. Everything else is
#: fleet-owned and the detail page states that instead of offering actions.
CLERK_STATES: frozenset[CaseState] = frozenset(
    {
        CaseState.PENDING_HUMAN,
        CaseState.QUARANTINED,
        CaseState.APPROVED,
        CaseState.ISSUED,
        CaseState.DENIED,
    }
)

_LABELS: dict[CaseState, str] = {
    CaseState.APPROVED: "Approve",
    CaseState.DENIED: "Deny",
    CaseState.INFO_REQUESTED: "Request info",
    CaseState.ISSUED: "Issue permit",
    CaseState.CLOSED: "Close case",
    CaseState.IN_REVIEW: "Re-admit for review",
}

_LABEL_OVERRIDES: dict[tuple[CaseState, CaseState], str] = {
    (CaseState.QUARANTINED, CaseState.CLOSED): "Discard",
}

_SLUGS: dict[CaseState, str] = {
    CaseState.APPROVED: "approve",
    CaseState.DENIED: "deny",
    CaseState.INFO_REQUESTED: "request_info",
    CaseState.ISSUED: "issue",
    CaseState.CLOSED: "close",
    CaseState.IN_REVIEW: "readmit",
}

_SLUG_OVERRIDES: dict[tuple[CaseState, CaseState], str] = {
    (CaseState.QUARANTINED, CaseState.CLOSED): "discard",
}

#: §5 defines no per-decision topics beyond ``action.approved``, so every
#: human decision at the gate rides that topic with the payload naming the
#: exact action; re-admission re-requests review; closure is ``case.closed``.
#: Recorded as an honest §5 note in PROGRESS rather than inventing topics.
_EVENTS: dict[CaseState, EventType] = {
    CaseState.APPROVED: EventType.ACTION_APPROVED,
    CaseState.DENIED: EventType.ACTION_APPROVED,
    CaseState.INFO_REQUESTED: EventType.ACTION_APPROVED,
    CaseState.ISSUED: EventType.ACTION_APPROVED,
    CaseState.IN_REVIEW: EventType.REVIEW_REQUESTED,
    CaseState.CLOSED: EventType.CASE_CLOSED,
}


@dataclass(frozen=True)
class ClerkAction:
    """One button the clerk may press in the current state."""

    target: CaseState
    slug: str
    label: str
    needs_approval_row: bool
    event_type: EventType


def clerk_actions(state: CaseState) -> list[ClerkAction]:
    """The legal clerk actions from ``state``, derived from the contract."""
    if state not in CLERK_STATES:
        return []
    actions = []
    for target in sorted(ALLOWED_TRANSITIONS[state], key=lambda s: s.value):
        actions.append(
            ClerkAction(
                target=target,
                slug=_SLUG_OVERRIDES.get((state, target), _SLUGS[target]),
                label=_LABEL_OVERRIDES.get((state, target), _LABELS[target]),
                needs_approval_row=target in APPROVAL_REQUIRED_TARGETS,
                event_type=_EVENTS[target],
            )
        )
    return actions


def fleet_owns(state: CaseState) -> bool:
    """True when no clerk action exists because the fleet owns this state."""
    return state not in CLERK_STATES and state is not CaseState.CLOSED
