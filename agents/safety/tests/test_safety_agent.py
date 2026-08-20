"""Safety agent structure + schema parity (bundle copies must not drift)."""

from civicnexus.contracts import Application, Citation, DeterminationOutcome, ReviewFinding
from safety_agent.agent import root_agent
from safety_agent.rag_tool import lookup_municipal_code
from safety_agent.schemas import ApplicationOut, CitationOut, Outcome, ReviewFindingOut


def test_outcome_parity() -> None:
    assert {o.value for o in Outcome} == {o.value for o in DeterminationOutcome}


def test_schema_parity() -> None:
    assert set(ReviewFindingOut.model_fields) == set(ReviewFinding.model_fields)
    assert set(CitationOut.model_fields) == set(Citation.model_fields)
    assert set(ApplicationOut.model_fields) == set(Application.model_fields)


def test_structure() -> None:
    assert root_agent.name == "safety"
    assert lookup_municipal_code in list(root_agent.tools)
    assert root_agent.output_schema is ReviewFindingOut
