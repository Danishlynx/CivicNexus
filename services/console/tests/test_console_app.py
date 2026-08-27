"""Console HTTP surface tests with stores faked (no GCP, no emulator)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from civicnexus.contracts import Applicant, Case, CaseState
from console.app import RefusingPublisher, create_app, get_case_store, resolve_mode
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeCaseStore:
    def __init__(self, cases: list[Case], invalid: list[str]) -> None:
        self._cases = cases
        self._invalid = invalid

    def list_cases(self) -> tuple[list[Case], list[str]]:
        ordered = sorted(self._cases, key=lambda c: c.updated_at, reverse=True)
        return ordered, self._invalid


def _case(case_id: str, *, state: CaseState = CaseState.PENDING_HUMAN, age: int = 0) -> Case:
    base = Case(
        case_id=case_id,
        permit_type="garage_conversion",
        applicant=Applicant(name="Synthetic Rosa CANARY-ROSA-NAME-2b8e", email="r@example.test"),
        state=state,
    )
    return base.model_copy(update={"updated_at": datetime.now(UTC) - timedelta(minutes=age)})


def _client(app: FastAPI, cases: list[Case], invalid: list[str] | None = None) -> TestClient:
    fake = FakeCaseStore(cases, invalid or [])
    app.dependency_overrides[get_case_store] = lambda: fake
    return TestClient(app)


@pytest.fixture()
def reader() -> Generator[TestClient, None, None]:
    app = create_app("reader")
    yield _client(app, [_case("case-b", age=10), _case("case-a", age=1)])
    app.dependency_overrides.clear()


class TestModeResolution:
    def test_default_is_reader(self) -> None:
        assert resolve_mode(None) == "reader"
        assert resolve_mode("") == "reader"

    def test_unknown_value_fails_closed_to_reader(self) -> None:
        assert resolve_mode("admin") == "reader"
        assert resolve_mode("CLERK") == "reader"  # exact match only

    def test_clerk_is_explicit(self) -> None:
        assert resolve_mode("clerk") == "clerk"


class TestReaderSurface:
    def test_healthz(self, reader: TestClient) -> None:
        response = reader.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_queue_renders_cases_newest_first(self, reader: TestClient) -> None:
        html = reader.get("/").text
        assert html.index("case-a") < html.index("case-b")
        assert "PENDING_HUMAN" in html
        assert "PUBLIC · READ-ONLY" in html

    def test_synthetic_data_footer_on_every_page(self, reader: TestClient) -> None:
        html = reader.get("/").text
        assert "All data synthetic" in html
        assert "CANARY-*" in html

    def test_queue_reports_invalid_documents(self) -> None:
        app = create_app("reader")
        client = _client(app, [_case("case-ok")], invalid=["case-broken"])
        try:
            html = client.get("/").text
            assert "1 document failed" in html
        finally:
            app.dependency_overrides.clear()

    def test_api_cases_shape(self, reader: TestClient) -> None:
        body = reader.get("/api/cases").json()
        assert [c["case_id"] for c in body["cases"]] == ["case-a", "case-b"]
        assert body["excluded_invalid_ids"] == []

    def test_write_route_not_mounted_in_reader_mode(self, reader: TestClient) -> None:
        # D2: in reader mode the action route DOES NOT EXIST - a 404, not a
        # 403 with a handler behind it.
        response = reader.post("/cases/case-a/action", data={"action": "approve"})
        assert response.status_code == 404

    def test_applicant_content_is_escaped(self) -> None:
        # D13/XSS: applicant-influenceable strings must render inert.
        app = create_app("reader")
        hostile = _case("case-x").model_copy(
            update={"applicant": Applicant(name="<script>alert(1)</script>", email="x@e.test")}
        )
        client = _client(app, [hostile])
        try:
            html = client.get("/").text
            assert "<script>alert(1)</script>" not in html
            assert "&lt;script&gt;" in html
        finally:
            app.dependency_overrides.clear()


class TestRefusingPublisher:
    def test_reader_publisher_refuses(self) -> None:
        publisher = RefusingPublisher()
        with pytest.raises(RuntimeError, match="reader mode cannot publish"):
            publisher.publish(None)  # type: ignore[arg-type]


class TestClerkMounting:
    def test_clerk_app_mounts_read_routes_too(self) -> None:
        app = create_app("clerk")
        fake = FakeCaseStore([_case("case-a")], [])
        app.dependency_overrides[get_case_store] = lambda: fake
        try:
            client = TestClient(app)
            assert client.get("/healthz").status_code == 200
            assert "case-a" in client.get("/").text
            assert "CLERK" in client.get("/").text
        finally:
            app.dependency_overrides.clear()
