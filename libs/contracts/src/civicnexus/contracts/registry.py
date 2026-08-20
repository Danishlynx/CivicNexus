"""Agent registry contracts (§3.1, §6.2): cards, versions, approval lifecycle.

An agent version is dispatchable only while its card is APPROVED. Registration
lands in PENDING — a human approves; the watchdog (or a human) quarantines;
only a human clears quarantine (§7.2). The gateway and coordinator consult the
registry on every dispatch, which is what makes hot-add possible: approval of
a new card is instantly effective, no redeploy anywhere.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AgentStatus(StrEnum):
    """Card lifecycle states, per §6.2 / §11 Phase 3."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    QUARANTINED = "QUARANTINED"


#: Legal lifecycle moves. PENDING cards can also be quarantined outright
#: (a registered-but-suspicious card must be freezable before approval).
REGISTRY_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.PENDING: frozenset({AgentStatus.APPROVED, AgentStatus.QUARANTINED}),
    AgentStatus.APPROVED: frozenset({AgentStatus.QUARANTINED}),
    AgentStatus.QUARANTINED: frozenset({AgentStatus.APPROVED}),
}

#: Status changes a machine may perform without a human actor: only the
#: watchdog's quarantine of an approved agent (§7.2). Everything else —
#: approval, un-quarantine — names a human.
MACHINE_ALLOWED_CHANGES: frozenset[tuple[AgentStatus, AgentStatus]] = frozenset(
    {(AgentStatus.APPROVED, AgentStatus.QUARANTINED)}
)


def can_change_status(current: AgentStatus, target: AgentStatus, *, human_actor: bool) -> bool:
    """Whether the lifecycle permits this move for this kind of actor."""
    if target not in REGISTRY_TRANSITIONS[current]:
        return False
    if human_actor:
        return True
    return (current, target) in MACHINE_ALLOWED_CHANGES


class AgentCard(BaseModel):
    """One registered agent version. The (agent_id, version) pair is the key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    display_name: str
    description: str
    capabilities: list[str] = Field(min_length=1)
    endpoint: str = Field(description="A2A endpoint or engine resource name")
    status: AgentStatus = AgentStatus.PENDING
    registered_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status_changed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status_changed_by: str = ""

    @property
    def key(self) -> str:
        """Firestore document id for this card."""
        return f"{self.agent_id}@{self.version}"
