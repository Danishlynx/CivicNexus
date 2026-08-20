"""HTTP surface tests with the store faked (no GCP, no emulator)."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from civicnexus.contracts import AgentCard, AgentStatus, can_change_status
from fastapi.testclient import TestClient
from registry.app import app, get_store
from registry.store import DuplicateCardError, LifecycleError, UnknownCardError


class FakeStore:
    def __init__(self) -> None:
        self.cards: dict[str, AgentCard] = {}

    def register(self, card: AgentCard) -> AgentCard:
        pending = card.model_copy(update={"status": AgentStatus.PENDING})
        if pending.key in self.cards:
            raise DuplicateCardError(pending.key)
        self.cards[pending.key] = pending
        return pending

    def get(self, agent_id: str, version: str) -> AgentCard:
        try:
            return self.cards[f"{agent_id}@{version}"]
        except KeyError as exc:
            raise UnknownCardError(f"{agent_id}@{version}") from exc

    def change_status(
        self, agent_id: str, version: str, target: AgentStatus, *, actor: str, human_actor: bool
    ) -> AgentCard:
        card = self.get(agent_id, version)
        if not can_change_status(card.status, target, human_actor=human_actor):
            raise LifecycleError("not permitted")
        updated = card.model_copy(
            update={
                "status": target,
                "status_changed_by": actor,
                "status_changed_at": datetime.now(UTC),
            }
        )
        self.cards[card.key] = updated
        return updated

    def find(self, *, capability: Any = None, status: Any = None) -> list[AgentCard]:
        out = [
            c
            for c in self.cards.values()
            if (capability is None or capability in c.capabilities)
            and (status is None or c.status == status)
        ]
        return sorted(out, key=lambda c: c.key)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    fake = FakeStore()
    app.dependency_overrides[get_store] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


CARD = {
    "agent_id": "tree-preservation",
    "version": "1.0.0",
    "display_name": "Tree preservation reviewer",
    "description": "Reviews protected-tree impact.",
    "capabilities": ["tree_preservation"],
    "endpoint": "projects/p/locations/l/reasoningEngines/42",
}


def test_register_returns_pending(client: TestClient) -> None:
    response = client.post("/agents", json=CARD)
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"


def test_duplicate_register_409(client: TestClient) -> None:
    client.post("/agents", json=CARD)
    assert client.post("/agents", json=CARD).status_code == 409


def test_approve_then_discover(client: TestClient) -> None:
    client.post("/agents", json=CARD)
    response = client.post(
        "/agents/tree-preservation/1.0.0/approve",
        json={"actor": "clerk@example.test", "human_actor": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    found = client.get("/agents", params={"capability": "tree_preservation", "status": "APPROVED"})
    assert [c["agent_id"] for c in found.json()] == ["tree-preservation"]


def test_machine_approval_403(client: TestClient) -> None:
    client.post("/agents", json=CARD)
    response = client.post(
        "/agents/tree-preservation/1.0.0/approve",
        json={"actor": "watchdog", "human_actor": False},
    )
    assert response.status_code == 403


def test_unknown_card_404(client: TestClient) -> None:
    assert client.get("/agents/ghost/1.0.0").status_code == 404


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
