"""Unit tests: circuit breaker detection and incident store (no GCP)."""

from typing import Any

import pytest
from civicnexus.contracts import Incident, IncidentKind, IncidentStatus, ScreeningPoint
from civicnexus.tools import CircuitBreaker, IncidentStore, loop_signature

TRACEPARENT = "00-" + "ab" * 16 + "-" + "cd" * 8 + "-01"


class TestCircuitBreaker:
    def test_opens_exactly_at_threshold_and_only_once(self) -> None:
        breaker = CircuitBreaker()
        args = {"section": "17.44.100"}
        assert not breaker.observe("case-1", "zoning", "consult", args)
        assert not breaker.observe("case-1", "zoning", "consult", args)
        assert breaker.observe("case-1", "zoning", "consult", args)  # trips here
        assert not breaker.observe("case-1", "zoning", "consult", args)  # already open
        assert breaker.is_open("case-1", "zoning", "consult", args)

    def test_different_args_do_not_trip(self) -> None:
        breaker = CircuitBreaker()
        for section in ("17.44.100", "17.44.110", "17.44.120"):
            assert not breaker.observe("case-1", "zoning", "consult", {"section": section})

    def test_cases_are_isolated(self) -> None:
        breaker = CircuitBreaker()
        args = {"q": "same"}
        breaker.observe("case-1", "zoning", "consult", args)
        breaker.observe("case-1", "zoning", "consult", args)
        assert not breaker.observe("case-2", "zoning", "consult", args)

    def test_signature_is_stable_under_key_order(self) -> None:
        a = loop_signature("zoning", "consult", {"a": 1, "b": 2})
        b = loop_signature("zoning", "consult", {"b": 2, "a": 1})
        assert a == b


class _FakeSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], key: str) -> None:
        self._store = store
        self._key = key

    def create(self, data: dict[str, Any]) -> None:
        if self._key in self._store:
            raise RuntimeError(f"already exists: {self._key}")
        self._store[self._key] = data

    def update(self, patch: dict[str, Any]) -> None:
        self._store[self._key].update(patch)

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._store.get(self._key))


class _FakeDb:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, _name: str) -> "_FakeDb":
        return self

    def document(self, key: str) -> _FakeDoc:
        return _FakeDoc(self.docs, key)


def _incident() -> Incident:
    return Incident(
        incident_id="inc-42",
        case_id="case-42",
        kind=IncidentKind.ARMOR_SCREENING,
        cause="pi_and_jailbreak MATCH_FOUND at HIGH",
        screening_point=ScreeningPoint.INBOUND_CONTENT,
        traceparent=TRACEPARENT,
        actor="demo_injection",
    )


class TestIncidentStore:
    def test_record_and_get_round_trip(self) -> None:
        store = IncidentStore(_FakeDb())
        store.record(_incident())
        loaded = store.get("inc-42")
        assert loaded.case_id == "case-42"
        assert loaded.status is IncidentStatus.OPEN

    def test_duplicate_record_is_loud(self) -> None:
        store = IncidentStore(_FakeDb())
        store.record(_incident())
        with pytest.raises(RuntimeError, match="already exists"):
            store.record(_incident())

    def test_resolve_requires_named_human(self) -> None:
        store = IncidentStore(_FakeDb())
        store.record(_incident())
        with pytest.raises(ValueError, match="named human"):
            store.resolve("inc-42", resolved_by="")
        resolved = store.resolve("inc-42", resolved_by="danishlynx@gmail.com")
        assert resolved.status is IncidentStatus.RESOLVED
        assert store.get("inc-42").status is IncidentStatus.RESOLVED

    def test_get_missing_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            IncidentStore(_FakeDb()).get("inc-missing")
