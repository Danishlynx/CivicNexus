"""Tree-preservation agent structure + schema parity."""

from civicnexus.contracts import Citation, DeterminationOutcome, ReviewFinding
from treepres_agent.agent import root_agent
from treepres_agent.rag_tool import lookup_municipal_code
from treepres_agent.schemas import CitationOut, Outcome, ReviewFindingOut


def test_outcome_parity() -> None:
    assert {o.value for o in Outcome} == {o.value for o in DeterminationOutcome}


def test_schema_parity() -> None:
    assert set(ReviewFindingOut.model_fields) == set(ReviewFinding.model_fields)
    assert set(CitationOut.model_fields) == set(Citation.model_fields)


def test_structure() -> None:
    assert root_agent.name == "tree_preservation"
    assert lookup_municipal_code in list(root_agent.tools)
    assert root_agent.output_schema is ReviewFindingOut
