"""Guard against drift between agent-local schemas and libs/contracts.

The caseflow bundle duplicates its model-output shapes for deployment
self-containment (see schemas.py docstring); these tests make that duplication
safe — any divergence fails the build.
"""

from caseflow_agent.schemas import (
    ApplicationOut,
    CitationOut,
    FactSheetOut,
    FactStatusOut,
    Outcome,
    ProvisionFactOut,
    ReviewFindingOut,
)
from civicnexus.contracts import (
    Application,
    Citation,
    DeterminationOutcome,
    ReviewFinding,
)
from civicnexus.decision import FactSheet, FactStatus, ProvisionFact


def test_outcome_values_match() -> None:
    assert {o.value for o in Outcome} == {o.value for o in DeterminationOutcome}


def test_citation_fields_match() -> None:
    assert set(CitationOut.model_fields) == set(Citation.model_fields)


def test_review_finding_fields_match() -> None:
    assert set(ReviewFindingOut.model_fields) == {f for f in ReviewFinding.model_fields}


def test_application_fields_match() -> None:
    assert set(ApplicationOut.model_fields) == set(Application.model_fields)


def test_review_finding_round_trips_into_contract() -> None:
    finding = ReviewFindingOut(
        outcome=Outcome.APPROVE,
        citations=[CitationOut(chunk_id="17.44.100", quote="verbatim span")],
        rationale="r",
        confidence=0.5,
    )
    contract = ReviewFinding.model_validate(finding.model_dump())
    assert contract.citations[0].chunk_id == "17.44.100"


def test_application_round_trips_into_contract() -> None:
    app = ApplicationOut(
        applicant_name="Synthetic Maria",
        applicant_email="maria@example.test",
        permit_type="garage_conversion",
        project_description="garage to bakery",
        complete=True,
    )
    contract = Application.model_validate(app.model_dump())
    assert contract.complete is True


def test_fact_status_values_match() -> None:
    assert {s.value for s in FactStatusOut} == {s.value for s in FactStatus}


def test_provision_fact_fields_match() -> None:
    assert set(ProvisionFactOut.model_fields) == set(ProvisionFact.model_fields)


def test_fact_sheet_fields_match() -> None:
    assert set(FactSheetOut.model_fields) == set(FactSheet.model_fields)


def test_fact_sheet_round_trips_into_the_decision_library() -> None:
    out = FactSheetOut(
        permit_type="home_occupation",
        facts=[
            ProvisionFactOut(
                provision="17.44.100(G)",
                element="rooms_used",
                status=FactStatusOut.SATISFIED,
                stated_value="one room",
                quote="convert one room of my attached garage",
            )
        ],
    )
    sheet = FactSheet.model_validate(out.model_dump())
    assert sheet.get_by_element("17.44.100/rooms_used") is not None
