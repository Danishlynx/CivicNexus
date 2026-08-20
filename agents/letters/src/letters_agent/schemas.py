"""Model-facing schema, deploy-bundle-local copy (parity-tested against contracts)."""

from pydantic import BaseModel, ConfigDict, Field


class LetterDraftOut(BaseModel):
    """Mirror of contracts.LetterDraft."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tone: str = "professional"
