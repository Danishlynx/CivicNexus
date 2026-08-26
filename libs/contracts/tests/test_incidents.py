"""Incident contract tests (ADR-006 D6/D12)."""

import pytest
from civicnexus.contracts import (
    FilterMatch,
    Incident,
    IncidentKind,
    IncidentStatus,
    ScreeningPoint,
)
from pydantic import ValidationError

TRACEPARENT = "00-" + "ab" * 16 + "-" + "cd" * 8 + "-01"


def _armor_incident(**overrides: object) -> Incident:
    fields: dict[str, object] = {
        "incident_id": "inc-0001",
        "case_id": "case-0001",
        "kind": IncidentKind.ARMOR_SCREENING,
        "cause": "pi_and_jailbreak MATCH_FOUND at HIGH",
        "screening_point": ScreeningPoint.INBOUND_CONTENT,
        "filter_matches": [
            FilterMatch(filter="pi_and_jailbreak", match_state="MATCH_FOUND", confidence="HIGH")
        ],
        "quarantine_uri": "gs://bucket/case-0001/poisoned.pdf",
        "traceparent": TRACEPARENT,
        "actor": "demo_injection",
    }
    fields.update(overrides)
    return Incident.model_validate(fields)


def test_armor_incident_validates_and_defaults_open() -> None:
    incident = _armor_incident()
    assert incident.status is IncidentStatus.OPEN
    assert incident.ts.tzinfo is not None


def test_armor_incident_requires_screening_point() -> None:
    with pytest.raises(ValidationError, match="screening_point"):
        _armor_incident(screening_point=None)


def test_breaker_incident_needs_no_screening_point() -> None:
    incident = _armor_incident(
        kind=IncidentKind.CIRCUIT_BREAKER,
        cause="3 identical calls: zoning/consult sha256:deadbeef",
        screening_point=None,
        filter_matches=[],
        quarantine_uri="",
    )
    assert incident.screening_point is None


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        _armor_incident(surprise="field")


def test_payload_round_trips_as_json_shapes() -> None:
    payload = _armor_incident().as_payload()
    assert payload["kind"] == "armor_screening"
    assert payload["screening_point"] == "inbound_content"
    assert payload["filter_matches"][0]["confidence"] == "HIGH"
    assert isinstance(payload["ts"], str)
