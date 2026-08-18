"""Integration tests for CaseStore against the Firestore emulator.

Skipped automatically when FIRESTORE_EMULATOR_HOST is unset — start the
emulators with ``docker compose -f docker-compose.emulators.yaml up -d`` (see
docs/runbooks/emulators.md). Pub/Sub publishing is faked here; its wire
behavior is covered by the unit tests and the deployed smoke path.
"""

import os
import uuid

import pytest
from civicnexus.contracts import (
    Actor,
    Applicant,
    Case,
    CaseState,
    Citation,
    Determination,
    DeterminationOutcome,
    EventType,
)
from civicnexus.tools import CaseStore, HumanActionRequiredError, IllegalTransitionError

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="FIRESTORE_EMULATOR_HOST not set (emulator not running)",
)

TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


class _CapturingPublisher:
    def __init__(self) -> None:
        self.published: list[str] = []

    def publish(self, envelope) -> str:  # type: ignore[no-untyped-def]
        self.published.append(envelope.type.value)
        return f"fake-{len(self.published)}"


@pytest.fixture()
def store() -> tuple[CaseStore, _CapturingPublisher]:
    from google.cloud import firestore

    db = firestore.Client(project="civicnexus-emulator")
    publisher = _CapturingPublisher()
    return (
        CaseStore(db, publisher, Actor(agent_id="test", agent_version="0.0.0")),  # type: ignore[arg-type]
        publisher,
    )


def _new_case() -> Case:
    return Case(
        case_id=f"case-{uuid.uuid4().hex[:12]}",
        permit_type="garage_conversion",
        applicant=Applicant(name="Synthetic Maria", email="maria@example.test"),
    )


def test_create_and_read_back(store: tuple[CaseStore, _CapturingPublisher]) -> None:
    cs, pub = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    loaded = cs.get_case(case.case_id)
    assert loaded.state is CaseState.RECEIVED
    assert loaded.applicant.email == "maria@example.test"
    assert pub.published == ["case.received"]


def test_duplicate_create_fails(store: tuple[CaseStore, _CapturingPublisher]) -> None:
    cs, _ = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    with pytest.raises(Exception):  # noqa: B017 - emulator raises Conflict/AlreadyExists
        cs.create_case(case, traceparent=TRACEPARENT)


def test_legal_transition_chain(store: tuple[CaseStore, _CapturingPublisher]) -> None:
    cs, pub = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    cs.transition(case.case_id, CaseState.TRIAGED, EventType.CASE_TRIAGED, traceparent=TRACEPARENT)
    cs.transition(
        case.case_id, CaseState.IN_REVIEW, EventType.REVIEW_REQUESTED, traceparent=TRACEPARENT
    )
    updated = cs.transition(
        case.case_id, CaseState.PENDING_HUMAN, EventType.REVIEW_COMPLETED, traceparent=TRACEPARENT
    )
    assert updated.state is CaseState.PENDING_HUMAN
    assert pub.published == [
        "case.received",
        "case.triaged",
        "review.requested",
        "review.completed",
    ]


def test_illegal_transition_refused_and_state_unchanged(
    store: tuple[CaseStore, _CapturingPublisher],
) -> None:
    cs, pub = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    with pytest.raises(IllegalTransitionError):
        cs.transition(
            case.case_id, CaseState.ISSUED, EventType.CASE_CLOSED, traceparent=TRACEPARENT
        )
    assert cs.get_case(case.case_id).state is CaseState.RECEIVED
    assert pub.published == ["case.received"]


def test_human_gate_enforced_at_store_level(
    store: tuple[CaseStore, _CapturingPublisher],
) -> None:
    cs, _ = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    cs.transition(case.case_id, CaseState.TRIAGED, EventType.CASE_TRIAGED, traceparent=TRACEPARENT)
    cs.transition(
        case.case_id, CaseState.IN_REVIEW, EventType.REVIEW_REQUESTED, traceparent=TRACEPARENT
    )
    cs.transition(
        case.case_id, CaseState.PENDING_HUMAN, EventType.REVIEW_COMPLETED, traceparent=TRACEPARENT
    )
    with pytest.raises(HumanActionRequiredError):
        cs.transition(
            case.case_id,
            CaseState.APPROVED,
            EventType.ACTION_APPROVED,
            traceparent=TRACEPARENT,
            human_actor=False,
        )
    updated = cs.transition(
        case.case_id,
        CaseState.APPROVED,
        EventType.ACTION_APPROVED,
        traceparent=TRACEPARENT,
        human_actor=True,
    )
    assert updated.state is CaseState.APPROVED


def test_determination_append(store: tuple[CaseStore, _CapturingPublisher]) -> None:
    cs, pub = store
    case = _new_case()
    cs.create_case(case, traceparent=TRACEPARENT)
    det = Determination(
        agent_id="zoning",
        agent_version="0.1.0",
        outcome=DeterminationOutcome.APPROVE,
        citations=[Citation(chunk_id="17.44.100", quote="Not more than one room")],
        rationale="meets home-occupation conditions",
        confidence=0.8,
    )
    cs.add_determination(case.case_id, det, traceparent=TRACEPARENT)
    loaded = cs.get_case(case.case_id)
    assert len(loaded.determinations) == 1
    assert loaded.determinations[0].citations[0].chunk_id == "17.44.100"
    assert pub.published[-1] == "review.completed"


def test_event_dedup(store: tuple[CaseStore, _CapturingPublisher]) -> None:
    cs, _ = store
    event_id = f"evt-{uuid.uuid4().hex}"
    assert cs.record_event_once(event_id) is True
    assert cs.record_event_once(event_id) is False
