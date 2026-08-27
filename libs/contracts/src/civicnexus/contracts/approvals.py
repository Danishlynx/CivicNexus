"""Approval record for human-gated transitions (§4, §6.2/§6.4 per ADR-007 D3).

The §4 guard reads: "no transition into ISSUED, DENIED, or any letter send
without a row in approvals/". This model IS that row. It is minted by
``ApprovalStore`` (libs/tools) when a named human acts, and verified inside
``CaseStore.transition`` — never in the caller, because a check the caller
performs is a check the caller can skip.

``approval_token`` is recorded per §6.2 for a future consumer; no send path
exists in the codebase today, so consumption plumbing is deliberately not
built (ADR-007 D3). The token is never logged.
"""

from datetime import UTC, datetime

from civicnexus.contracts.case import APPROVAL_REQUIRED_TARGETS, CaseState
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Approval(BaseModel):
    """One human approval, keyed by ``approval_id`` in Firestore ``approvals/``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: str
    case_id: str
    action: str
    target_state: CaseState
    approver: str
    approval_token: str
    traceparent: str
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _guards(self) -> "Approval":
        if not self.approver.strip():
            raise ValueError("an approval must name a human approver")
        if not self.action.strip():
            raise ValueError("an approval must name the action taken")
        if self.target_state not in APPROVAL_REQUIRED_TARGETS:
            allowed = ", ".join(sorted(s.value for s in APPROVAL_REQUIRED_TARGETS))
            raise ValueError(f"approvals exist only for {allowed}; got {self.target_state.value}")
        return self
