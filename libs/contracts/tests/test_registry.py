"""Lifecycle tests for the agent registry contracts."""

import pytest
from civicnexus.contracts.registry import (
    AgentCard,
    AgentStatus,
    can_change_status,
)
from pydantic import ValidationError


def _card(**overrides: object) -> AgentCard:
    defaults: dict[str, object] = {
        "agent_id": "tree-preservation",
        "version": "1.0.0",
        "display_name": "Tree preservation reviewer",
        "description": "Reviews applications for protected-tree impact.",
        "capabilities": ["tree_preservation"],
        "endpoint": "projects/p/locations/l/reasoningEngines/123",
    }
    defaults.update(overrides)
    return AgentCard.model_validate(defaults)


class TestLifecycle:
    def test_human_can_approve_pending(self) -> None:
        assert can_change_status(AgentStatus.PENDING, AgentStatus.APPROVED, human_actor=True)

    def test_machine_cannot_approve(self) -> None:
        assert not can_change_status(AgentStatus.PENDING, AgentStatus.APPROVED, human_actor=False)

    def test_watchdog_may_quarantine_approved(self) -> None:
        assert can_change_status(AgentStatus.APPROVED, AgentStatus.QUARANTINED, human_actor=False)

    def test_only_human_clears_quarantine(self) -> None:
        assert can_change_status(AgentStatus.QUARANTINED, AgentStatus.APPROVED, human_actor=True)
        assert not can_change_status(
            AgentStatus.QUARANTINED, AgentStatus.APPROVED, human_actor=False
        )

    def test_no_backwards_moves(self) -> None:
        assert not can_change_status(AgentStatus.APPROVED, AgentStatus.PENDING, human_actor=True)
        assert not can_change_status(AgentStatus.QUARANTINED, AgentStatus.PENDING, human_actor=True)

    def test_pending_can_be_frozen(self) -> None:
        assert can_change_status(AgentStatus.PENDING, AgentStatus.QUARANTINED, human_actor=True)


class TestCard:
    def test_defaults_to_pending(self) -> None:
        assert _card().status is AgentStatus.PENDING

    def test_key_shape(self) -> None:
        assert _card().key == "tree-preservation@1.0.0"

    def test_requires_capability(self) -> None:
        with pytest.raises(ValidationError):
            _card(capabilities=[])

    def test_agent_id_pattern(self) -> None:
        with pytest.raises(ValidationError):
            _card(agent_id="Bad Name!")

    def test_version_pattern(self) -> None:
        with pytest.raises(ValidationError):
            _card(version="v1")

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            _card(admin=True)
