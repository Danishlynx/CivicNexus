"""A specialist reviewer's finding — the model-generated core of a Determination.

Identity fields (agent_id/agent_version/trace_id) are stamped by the calling
service, never asked of the model; the model produces only outcome, grounding,
and rationale. ``to_determination`` performs that stamping in one place.
"""

from civicnexus.contracts.determinations import Citation, Determination, DeterminationOutcome
from pydantic import BaseModel, ConfigDict, Field


class ReviewFinding(BaseModel):
    """What a specialist agent concludes, with mandatory grounding fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: DeterminationOutcome
    citations: list[Citation] = Field(min_length=1)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)

    def to_determination(
        self, *, agent_id: str, agent_version: str, trace_id: str = ""
    ) -> Determination:
        """Stamp caller-known identity onto the model-produced finding."""
        return Determination(
            agent_id=agent_id,
            agent_version=agent_version,
            outcome=self.outcome,
            citations=list(self.citations),
            rationale=self.rationale,
            confidence=self.confidence,
            trace_id=trace_id,
        )
