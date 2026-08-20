"""Letter draft contract (§3.1 letters agent: drafts only, can never send).

The recipient is hard-locked to the applicant of record by the calling
service — the model never chooses an address (§6.7 confused-deputy defense).
"""

from pydantic import BaseModel, ConfigDict, Field


class LetterDraft(BaseModel):
    """A drafted applicant letter awaiting human approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tone: str = "professional"
