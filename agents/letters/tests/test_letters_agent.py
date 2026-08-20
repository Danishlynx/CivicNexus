"""Letters agent: schema parity and the no-send-capability guarantee."""

from civicnexus.contracts import LetterDraft
from letters_agent.agent import root_agent
from letters_agent.schemas import LetterDraftOut


def test_schema_parity_with_contract() -> None:
    assert set(LetterDraftOut.model_fields) == set(LetterDraft.model_fields)


def test_draft_round_trips_into_contract() -> None:
    draft = LetterDraftOut(subject="Your permit", body="Dear applicant...")
    assert LetterDraft.model_validate(draft.model_dump()).tone == "professional"


def test_letters_agent_has_no_tools() -> None:
    """The confused-deputy defense in structural form: nothing to misuse."""
    assert list(root_agent.tools) == []


def test_output_schema_enforced() -> None:
    assert root_agent.output_schema is LetterDraftOut
