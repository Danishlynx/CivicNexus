"""Determination model (ARCHITECTURE.md §4) — a specialist agent's conclusion.

Citations use quote-and-verify (§6.4): the verifier string-matches each quoted
span against the actual corpus chunk, so a fabricated "the code says approve"
fails verification. ``verifier_report`` stays a free-form mapping until the
verifier subsystem defines its shape (§7.3, Phase 5).
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeterminationOutcome(StrEnum):
    """Allowed outcomes, verbatim from §4."""

    APPROVE = "approve"
    DENY = "deny"
    REQUEST_INFO = "request_info"


class Citation(BaseModel):
    """One grounding reference: a stable corpus chunk id and the quoted span."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    quote: str


class Determination(BaseModel):
    """A specialist agent's determination, verbatim field list from §4."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    agent_version: str
    outcome: DeterminationOutcome
    citations: list[Citation] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    verifier_report: dict[str, Any] | None = None
    trace_id: str = ""
