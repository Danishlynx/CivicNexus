"""Model round-trip and rejection tests for Case and Determination (§4)."""

import json
from datetime import datetime

import pytest
from civicnexus.contracts import (
    Applicant,
    Case,
    CaseState,
    Citation,
    Determination,
    DeterminationOutcome,
)
from pydantic import ValidationError


def _case(**overrides: object) -> Case:
    defaults: dict[str, object] = {
        "case_id": "case-0001",
        "permit_type": "garage_conversion",
        "applicant": Applicant(name="Synthetic Maria", email="maria@example.test"),
    }
    defaults.update(overrides)
    return Case.model_validate(defaults)


def _determination(**overrides: object) -> Determination:
    defaults: dict[str, object] = {
        "agent_id": "zoning",
        "agent_version": "0.1.0",
        "outcome": DeterminationOutcome.APPROVE,
        "citations": [Citation(chunk_id="17.44.030", quote="Accessory structures may…")],
        "rationale": "Conversion satisfies accessory-use requirements.",
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return Determination.model_validate(defaults)


def test_case_round_trips_through_json() -> None:
    case = _case(determinations=[_determination()])
    restored = Case.model_validate(json.loads(case.model_dump_json()))
    assert restored == case
    assert restored.determinations[0].citations[0].chunk_id == "17.44.030"


def test_case_defaults() -> None:
    case = _case()
    assert case.state is CaseState.RECEIVED
    assert case.budget.hops_used == 0
    assert case.docs == [] and case.timers == [] and case.determinations == []


def test_case_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _case(status="OPEN")


def test_case_rejects_unknown_state() -> None:
    with pytest.raises(ValidationError):
        _case(state="ARCHIVED")


def test_case_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError):
        _case(created_at=datetime(2026, 8, 18))  # deliberately naive


def test_determination_rejects_unknown_outcome() -> None:
    with pytest.raises(ValidationError):
        _determination(outcome="escalate")


def test_determination_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        _determination(confidence=1.5)
    with pytest.raises(ValidationError):
        _determination(confidence=-0.1)


def test_determination_field_set_matches_spec() -> None:
    assert set(Determination.model_fields) == {
        "agent_id",
        "agent_version",
        "outcome",
        "citations",
        "rationale",
        "confidence",
        "verifier_report",
        "trace_id",
    }


def test_case_field_set_matches_spec() -> None:
    assert set(Case.model_fields) == {
        "case_id",
        "permit_type",
        "applicant",
        "docs",
        "state",
        "determinations",
        "budget",
        "timers",
        "created_at",
        "updated_at",
        "trace_id",
    }
