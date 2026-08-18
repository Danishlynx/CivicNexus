"""Unit tests: §4 transition guards and event publishing (no GCP needed)."""

import json
from typing import Any

import pytest
from civicnexus.contracts import (
    Actor,
    Applicant,
    Case,
    CaseState,
    EventEnvelope,
    EventType,
)
from civicnexus.tools import (
    ApprovalRequiredError,
    EventPublisher,
    HumanActionRequiredError,
    IllegalTransitionError,
    validate_transition,
)


def _case(state: CaseState) -> Case:
    return Case(
        case_id="case-0001",
        permit_type="garage_conversion",
        applicant=Applicant(name="Synthetic Maria", email="maria@example.test"),
        state=state,
    )


class TestValidateTransition:
    def test_legal_machine_edge_passes(self) -> None:
        validate_transition(
            _case(CaseState.RECEIVED), CaseState.TRIAGED, human_actor=False, approval_id=None
        )

    def test_illegal_edge_raises(self) -> None:
        with pytest.raises(IllegalTransitionError):
            validate_transition(
                _case(CaseState.RECEIVED), CaseState.ISSUED, human_actor=False, approval_id=None
            )

    def test_pending_human_requires_human(self) -> None:
        with pytest.raises(HumanActionRequiredError):
            validate_transition(
                _case(CaseState.PENDING_HUMAN),
                CaseState.APPROVED,
                human_actor=False,
                approval_id=None,
            )

    def test_denied_requires_approval_id_even_for_human(self) -> None:
        with pytest.raises(ApprovalRequiredError):
            validate_transition(
                _case(CaseState.PENDING_HUMAN),
                CaseState.DENIED,
                human_actor=True,
                approval_id=None,
            )

    def test_denied_with_human_and_approval_passes(self) -> None:
        validate_transition(
            _case(CaseState.PENDING_HUMAN),
            CaseState.DENIED,
            human_actor=True,
            approval_id="approval-123",
        )

    def test_issued_requires_approval_id(self) -> None:
        with pytest.raises(ApprovalRequiredError):
            validate_transition(
                _case(CaseState.APPROVED), CaseState.ISSUED, human_actor=True, approval_id=None
            )

    def test_quarantine_entry_needs_no_human(self) -> None:
        validate_transition(
            _case(CaseState.IN_REVIEW), CaseState.QUARANTINED, human_actor=False, approval_id=None
        )

    def test_info_requested_is_human_but_needs_no_approval(self) -> None:
        validate_transition(
            _case(CaseState.PENDING_HUMAN),
            CaseState.INFO_REQUESTED,
            human_actor=True,
            approval_id=None,
        )


class _FakeFuture:
    def result(self, timeout: float | None = None) -> str:
        return "msg-42"


class _FakePublisherClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def publish(self, topic_path: str, data: bytes, **attrs: str) -> _FakeFuture:
        self.calls.append((topic_path, data, attrs))
        return _FakeFuture()


class TestEventPublisher:
    def _publish_one(self) -> tuple[_FakePublisherClient, Any]:
        fake = _FakePublisherClient()
        publisher = EventPublisher("test-project", client=fake)
        envelope = EventEnvelope(
            type=EventType.CASE_RECEIVED,
            case_id="case-0001",
            actor=Actor(agent_id="api", agent_version="0.1.0"),
            traceparent="00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        )
        message_id = publisher.publish(envelope)
        return fake, message_id

    def test_topic_path_is_event_type(self) -> None:
        fake, _ = self._publish_one()
        assert fake.calls[0][0] == "projects/test-project/topics/case.received"

    def test_payload_round_trips_as_envelope(self) -> None:
        fake, _ = self._publish_one()
        restored = EventEnvelope.model_validate(json.loads(fake.calls[0][1]))
        assert restored.case_id == "case-0001"
        assert restored.type is EventType.CASE_RECEIVED

    def test_traceparent_rides_as_attribute(self) -> None:
        fake, _ = self._publish_one()
        attrs = fake.calls[0][2]
        assert attrs["traceparent"].startswith("00-0af76519")
        assert attrs["case_id"] == "case-0001"
        assert attrs["event_type"] == "case.received"

    def test_returns_message_id(self) -> None:
        _, message_id = self._publish_one()
        assert message_id == "msg-42"
