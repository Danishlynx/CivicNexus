"""Firestore-backed registry store — the single writer of ``registry_agents/``.

Lifecycle legality comes from the shared contract (`can_change_status`), so
the service cannot drift from what the tests and the gateway believe. Every
mutation emits one audit log line (``audit: true`` → BigQuery sink).
"""

from datetime import UTC, datetime
from typing import Any

from civicnexus.contracts import AgentCard, AgentStatus, can_change_status
from civicnexus.otel import get_logger

_log = get_logger("registry")

COLLECTION = "registry_agents"


class RegistryError(Exception):
    """Base error; message is safe to return to callers."""


class DuplicateCardError(RegistryError):
    """(agent_id, version) already registered."""


class UnknownCardError(RegistryError):
    """No such (agent_id, version)."""


class LifecycleError(RegistryError):
    """The requested status change is not permitted."""


class RegistryStore:
    """CRUD + lifecycle over agent cards."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def register(self, card: AgentCard) -> AgentCard:
        """Register a new card; status is forced to PENDING regardless of input."""
        pending = card.model_copy(
            update={
                "status": AgentStatus.PENDING,
                "status_changed_at": datetime.now(UTC),
                "status_changed_by": "",
            }
        )
        doc = self._db.collection(COLLECTION).document(pending.key)
        try:
            doc.create(pending.model_dump(mode="json"))
        except Exception as exc:
            raise DuplicateCardError(f"{pending.key} is already registered") from exc
        self._audit("agent.registered", pending, actor="")
        return pending

    def get(self, agent_id: str, version: str) -> AgentCard:
        snapshot = self._db.collection(COLLECTION).document(f"{agent_id}@{version}").get()
        if not snapshot.exists:
            raise UnknownCardError(f"{agent_id}@{version} is not registered")
        return AgentCard.model_validate(snapshot.to_dict())

    def change_status(
        self,
        agent_id: str,
        version: str,
        target: AgentStatus,
        *,
        actor: str,
        human_actor: bool,
    ) -> AgentCard:
        """Move a card through its lifecycle if the contract permits it."""
        card = self.get(agent_id, version)
        if not can_change_status(card.status, target, human_actor=human_actor):
            raise LifecycleError(
                f"{card.status.value} -> {target.value} is not permitted for "
                f"{'a human' if human_actor else 'a machine'} actor"
            )
        if human_actor and not actor:
            raise LifecycleError("human status changes must name the human actor")
        updated = card.model_copy(
            update={
                "status": target,
                "status_changed_at": datetime.now(UTC),
                "status_changed_by": actor,
            }
        )
        self._db.collection(COLLECTION).document(card.key).update(
            {
                "status": target.value,
                "status_changed_at": updated.status_changed_at,
                "status_changed_by": actor,
            }
        )
        self._audit(f"agent.{target.value.lower()}", updated, actor=actor)
        return updated

    def find(
        self, *, capability: str | None = None, status: AgentStatus | None = None
    ) -> list[AgentCard]:
        """Capability discovery. The coordinator asks for APPROVED cards only."""
        query = self._db.collection(COLLECTION)
        if capability is not None:
            query = query.where("capabilities", "array_contains", capability)
        if status is not None:
            query = query.where("status", "==", status.value)
        return sorted(
            (AgentCard.model_validate(s.to_dict()) for s in query.stream()),
            key=lambda c: c.key,
        )

    def _audit(self, action: str, card: AgentCard, *, actor: str) -> None:
        _log.info(
            f"{action} {card.key}",
            extra={
                "audit": True,
                "action": action,
                "agent_id": card.agent_id,
                "agent_version": card.version,
                "status": card.status.value,
                "capabilities": card.capabilities,
                "actor_id": actor or "system",
            },
        )
