"""Structured application produced by the intake agent (§2 workflow steps 1 and 2).

The intake agent's only job in Phase 1: turn messy applicant text into this
shape and say what's missing. Unknown fields are rejected like every contract.
"""

from pydantic import BaseModel, ConfigDict, Field


class Application(BaseModel):
    """A parsed permit application plus completeness triage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    applicant_name: str
    applicant_email: str
    permit_type: str
    project_description: str
    property_address: str = ""
    missing_items: list[str] = Field(default_factory=list)
    complete: bool
