"""Unit tests: store listing methods with per-document tolerance (ADR-007 D5).

``Case`` and ``Incident`` are ``frozen=True, extra="forbid"``, so one stray
field in one Firestore document would otherwise take down the whole console
queue. The listing methods must skip-and-report, never raise, and must sort in
Python because no composite index exists.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from civicnexus.contracts import (
    Actor,
    Applicant,
    Case,
    Incident,
    IncidentKind,
    ScreeningPoint,
)
from civicnexus.tools import CaseStore, IncidentStore

TRACEPARENT = "00-" + "ab" * 16 + "-" + "cd" * 8 + "-01"


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeListingDb:
    """Just enough Firestore for ``stream()``-based listings."""

    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._docs = docs

    def collection(self, _name: str) -> "_FakeListingDb":
        return self

    def stream(self) -> list[_FakeSnapshot]:
        return [_FakeSnapshot(doc_id, data) for doc_id, data in self._docs.items()]


class _NeverPublisher:
    def publish(self, envelope: Any) -> str:
        raise AssertionError("listing must never publish")


def _case(case_id: str, *, age_minutes: int) -> dict[str, Any]:
    base = Case(
        case_id=case_id,
        permit_type="garage_conversion",
        applicant=Applicant(name="Synthetic Rosa", email="rosa@example.test"),
    )
    stamped = base.model_copy(
        update={"updated_at": datetime.now(UTC) - timedelta(minutes=age_minutes)}
    )
    return stamped.model_dump(mode="json")


def _incident(incident_id: str, *, age_minutes: int) -> dict[str, Any]:
    inc = Incident(
        incident_id=incident_id,
        case_id="case-1",
        kind=IncidentKind.ARMOR_SCREENING,
        cause="pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE",
        screening_point=ScreeningPoint.INBOUND_CONTENT,
        traceparent=TRACEPARENT,
        actor="drill_runner",
    )
    stamped = inc.model_copy(update={"ts": datetime.now(UTC) - timedelta(minutes=age_minutes)})
    return stamped.model_dump(mode="json")


def _case_store(docs: dict[str, dict[str, Any]]) -> CaseStore:
    return CaseStore(
        _FakeListingDb(docs),
        _NeverPublisher(),  # type: ignore[arg-type]
        Actor(agent_id="test", agent_version="0.0.0"),
    )


class TestListCases:
    def test_sorted_newest_updated_first(self) -> None:
        docs = {
            "case-old": _case("case-old", age_minutes=30),
            "case-new": _case("case-new", age_minutes=1),
            "case-mid": _case("case-mid", age_minutes=10),
        }
        cases, invalid = _case_store(docs).list_cases()
        assert [c.case_id for c in cases] == ["case-new", "case-mid", "case-old"]
        assert invalid == []

    def test_one_malformed_doc_does_not_take_down_the_queue(self) -> None:
        broken = _case("case-broken", age_minutes=5)
        broken["not_a_field"] = "boom"  # extra="forbid" would 500 the page
        docs = {
            "case-ok": _case("case-ok", age_minutes=1),
            "case-broken": broken,
        }
        cases, invalid = _case_store(docs).list_cases()
        assert [c.case_id for c in cases] == ["case-ok"]
        assert invalid == ["case-broken"]

    def test_empty_collection(self) -> None:
        cases, invalid = _case_store({}).list_cases()
        assert cases == [] and invalid == []


class TestListIncidents:
    def test_sorted_newest_first_and_tolerant(self) -> None:
        broken = _incident("inc-broken", age_minutes=2)
        del broken["traceparent"]  # required field missing
        docs = {
            "inc-old": _incident("inc-old", age_minutes=60),
            "inc-new": _incident("inc-new", age_minutes=1),
            "inc-broken": broken,
        }
        incidents, invalid = IncidentStore(_FakeListingDb(docs)).list_incidents()
        assert [i.incident_id for i in incidents] == ["inc-new", "inc-old"]
        assert invalid == ["inc-broken"]
