"""Registry store integration tests against the Firestore emulator."""

import os
import uuid

import pytest
from civicnexus.contracts import AgentCard, AgentStatus
from registry.store import (
    DuplicateCardError,
    LifecycleError,
    RegistryStore,
    UnknownCardError,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="FIRESTORE_EMULATOR_HOST not set (emulator not running)",
)


@pytest.fixture()
def store() -> RegistryStore:
    from google.cloud import firestore

    return RegistryStore(firestore.Client(project="civicnexus-emulator"))


def _card(**overrides: object) -> AgentCard:
    defaults: dict[str, object] = {
        "agent_id": f"spike-{uuid.uuid4().hex[:8]}",
        "version": "1.0.0",
        "display_name": "Test agent",
        "description": "Test.",
        "capabilities": ["tree_preservation"],
        "endpoint": "projects/p/locations/l/reasoningEngines/1",
    }
    defaults.update(overrides)
    return AgentCard.model_validate(defaults)


def test_register_forces_pending(store: RegistryStore) -> None:
    registered = store.register(_card(status=AgentStatus.APPROVED))
    assert registered.status is AgentStatus.PENDING
    assert store.get(registered.agent_id, registered.version).status is AgentStatus.PENDING


def test_duplicate_registration_refused(store: RegistryStore) -> None:
    card = _card()
    store.register(card)
    with pytest.raises(DuplicateCardError):
        store.register(card)


def test_full_lifecycle_and_discovery(store: RegistryStore) -> None:
    card = store.register(_card())
    assert store.find(capability="tree_preservation", status=AgentStatus.APPROVED) == []

    approved = store.change_status(
        card.agent_id,
        card.version,
        AgentStatus.APPROVED,
        actor="clerk@example.test",
        human_actor=True,
    )
    assert approved.status is AgentStatus.APPROVED
    found = store.find(capability="tree_preservation", status=AgentStatus.APPROVED)
    assert any(c.key == card.key for c in found)

    quarantined = store.change_status(
        card.agent_id,
        card.version,
        AgentStatus.QUARANTINED,
        actor="watchdog",
        human_actor=False,
    )
    assert quarantined.status is AgentStatus.QUARANTINED
    assert not any(
        c.key == card.key
        for c in store.find(capability="tree_preservation", status=AgentStatus.APPROVED)
    )


def test_machine_cannot_approve(store: RegistryStore) -> None:
    card = store.register(_card())
    with pytest.raises(LifecycleError):
        store.change_status(
            card.agent_id, card.version, AgentStatus.APPROVED, actor="bot", human_actor=False
        )


def test_human_approval_must_be_named(store: RegistryStore) -> None:
    card = store.register(_card())
    with pytest.raises(LifecycleError):
        store.change_status(
            card.agent_id, card.version, AgentStatus.APPROVED, actor="", human_actor=True
        )


def test_unknown_card_raises(store: RegistryStore) -> None:
    with pytest.raises(UnknownCardError):
        store.get("nope", "9.9.9")
