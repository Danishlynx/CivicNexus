"""Model-facing output schemas, local copies for deployment self-containment.

The deployed bundle cannot import ``civicnexus.contracts`` (workspace libs are
not on the remote runtime's package index), so the two model-output shapes are
duplicated here. ``tests/test_schema_parity.py`` asserts field-for-field parity
with the contracts library — drift fails the build, so the duplication is safe.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Outcome(StrEnum):
    """Allowed determination outcomes (mirror of contracts.DeterminationOutcome)."""

    APPROVE = "approve"
    DENY = "deny"
    REQUEST_INFO = "request_info"


class CitationOut(BaseModel):
    """One grounding reference: section number + verbatim quoted span."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    quote: str


class ReviewFindingOut(BaseModel):
    """Zoning agent output (mirror of contracts.ReviewFinding)."""

    model_config = ConfigDict(extra="forbid")

    outcome: Outcome
    citations: list[CitationOut] = Field(min_length=1)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class FactStatusOut(StrEnum):
    """What the application says about one statute element.

    Mirror of ``civicnexus.decision.FactStatus``. No value names an outcome:
    the extraction agent reports facts and never reaches a conclusion.
    """

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    HEDGED = "hedged"
    ABSENT = "absent"


class ProvisionFactOut(BaseModel):
    """One statute element as read against one application (DECISION_MODE=code)."""

    model_config = ConfigDict(extra="forbid")

    provision: str
    element: str
    status: FactStatusOut
    stated_value: str = ""
    quote: str = ""


class FactSheetOut(BaseModel):
    """Extraction agent output (mirror of ``civicnexus.decision.FactSheet``)."""

    model_config = ConfigDict(extra="forbid")

    permit_type: str
    facts: list[ProvisionFactOut] = Field(default_factory=list)


class ApplicationOut(BaseModel):
    """Intake agent output (mirror of contracts.Application)."""

    model_config = ConfigDict(extra="forbid")

    applicant_name: str
    applicant_email: str
    permit_type: str
    project_description: str
    property_address: str = ""
    missing_items: list[str] = Field(default_factory=list)
    complete: bool
