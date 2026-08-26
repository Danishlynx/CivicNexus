"""State-machine legality tests against the §4 transition diagram."""

import pytest
from civicnexus.contracts import CaseState, can_transition, is_human_only

DOCUMENTED_EDGES = [
    (CaseState.RECEIVED, CaseState.TRIAGED),
    (CaseState.TRIAGED, CaseState.INCOMPLETE_AWAITING_APPLICANT),
    (CaseState.TRIAGED, CaseState.IN_REVIEW),
    (CaseState.INCOMPLETE_AWAITING_APPLICANT, CaseState.TRIAGED),
    (CaseState.IN_REVIEW, CaseState.VERIFICATION_FAILED),
    (CaseState.IN_REVIEW, CaseState.PENDING_HUMAN),
    (CaseState.IN_REVIEW, CaseState.PAUSED_BUDGET),
    (CaseState.VERIFICATION_FAILED, CaseState.IN_REVIEW),
    (CaseState.PAUSED_BUDGET, CaseState.PENDING_HUMAN),
    (CaseState.PENDING_HUMAN, CaseState.APPROVED),
    (CaseState.PENDING_HUMAN, CaseState.DENIED),
    (CaseState.PENDING_HUMAN, CaseState.INFO_REQUESTED),
    (CaseState.APPROVED, CaseState.ISSUED),
    (CaseState.ISSUED, CaseState.CLOSED),
    (CaseState.DENIED, CaseState.CLOSED),
    (CaseState.INFO_REQUESTED, CaseState.INCOMPLETE_AWAITING_APPLICANT),
]


@pytest.mark.parametrize(("src", "dst"), DOCUMENTED_EDGES)
def test_documented_edges_are_legal(src: CaseState, dst: CaseState) -> None:
    assert can_transition(src, dst)


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (CaseState.RECEIVED, CaseState.ISSUED),
        (CaseState.RECEIVED, CaseState.PENDING_HUMAN),
        (CaseState.TRIAGED, CaseState.APPROVED),
        (CaseState.IN_REVIEW, CaseState.ISSUED),
        (CaseState.IN_REVIEW, CaseState.APPROVED),
        (CaseState.APPROVED, CaseState.DENIED),
        (CaseState.CLOSED, CaseState.RECEIVED),
        (CaseState.PENDING_HUMAN, CaseState.ISSUED),
    ],
)
def test_shortcut_edges_are_illegal(src: CaseState, dst: CaseState) -> None:
    assert not can_transition(src, dst)


@pytest.mark.parametrize("src", [s for s in CaseState if s is not CaseState.QUARANTINED])
def test_any_state_may_quarantine(src: CaseState) -> None:
    assert can_transition(src, CaseState.QUARANTINED)


def test_quarantine_cannot_requarantine() -> None:
    assert not can_transition(CaseState.QUARANTINED, CaseState.QUARANTINED)


def test_quarantine_exits_are_exactly_readmit_and_discard() -> None:
    exits = {s for s in CaseState if can_transition(CaseState.QUARANTINED, s)}
    assert exits == {CaseState.IN_REVIEW, CaseState.CLOSED}


def test_quarantine_exits_require_a_human() -> None:
    assert is_human_only(CaseState.QUARANTINED)


def test_human_only_sources() -> None:
    assert is_human_only(CaseState.PENDING_HUMAN)
    assert is_human_only(CaseState.QUARANTINED)
    assert not is_human_only(CaseState.IN_REVIEW)


def test_verification_retry_loop_is_bounded_by_shape() -> None:
    assert can_transition(CaseState.IN_REVIEW, CaseState.VERIFICATION_FAILED)
    assert can_transition(CaseState.VERIFICATION_FAILED, CaseState.IN_REVIEW)
    assert not can_transition(CaseState.VERIFICATION_FAILED, CaseState.PENDING_HUMAN)
