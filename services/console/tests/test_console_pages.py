"""Detail page, clerk actions, incidents, and evals — stores faked (no GCP).

The clerk flow asserted here is the A10 exit walk in miniature: approve needs
no approvals row, issue and deny mint one and pass its REAL id into the
transition, and the store guard (not the route) is what refuses fabrication.

Clerk identity in these tests rides a crafted Bearer payload — the exact
claim-decode path the deployed service uses after Cloud Run has verified the
token. The form-field fallback is separately pinned to emulator-only.
"""

import base64
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from civicnexus.contracts import (
    Applicant,
    Approval,
    Case,
    CaseState,
    Citation,
    Determination,
    DeterminationOutcome,
    EventType,
    Incident,
    IncidentKind,
    IncidentStatus,
    ScreeningPoint,
)
from console.app import create_app, get_approval_store, get_case_store, get_incident_store
from fastapi import FastAPI
from fastapi.testclient import TestClient

TRACEPARENT = "00-" + "ab" * 16 + "-" + "cd" * 8 + "-01"


def _bearer(email: str) -> dict[str, str]:
    """A JWT-shaped token whose payload names ``email`` — the platform
    verifies signatures in production; the app only decodes the claim."""
    payload = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode()
    return {"Authorization": f"Bearer h.{payload}.s"}


def _case(case_id: str, *, state: CaseState = CaseState.PENDING_HUMAN) -> Case:
    return Case(
        case_id=case_id,
        permit_type="garage_conversion",
        applicant=Applicant(name="Synthetic Rosa", email="rosa@example.test"),
        state=state,
        determinations=[
            Determination(
                agent_id="zoning",
                agent_version="0.2.0",
                outcome=DeterminationOutcome.DENY,
                citations=[
                    Citation(chunk_id="17.44.100", quote="No employees are allowed"),
                ],
                rationale="non-resident helper named in the application",
                confidence=1.0,
                verifier_report={"passed": True, "checked": 1},
            )
        ],
        trace_id="ac70d29773a2694335410ef54538fed4",
    )


def _incident(incident_id: str = "inc-1", case_id: str = "case-q") -> Incident:
    return Incident(
        incident_id=incident_id,
        case_id=case_id,
        kind=IncidentKind.ARMOR_SCREENING,
        cause="pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE",
        screening_point=ScreeningPoint.INBOUND_CONTENT,
        quarantine_uri="gs://civicnexus-hack26-docs-quarantine/adv-002.pdf",
        traceparent=TRACEPARENT,
        actor="drill_runner",
    )


class FakeCaseStore:
    def __init__(self, cases: dict[str, Case]) -> None:
        self.cases = cases
        self.transitions: list[dict[str, Any]] = []

    def list_cases(self) -> tuple[list[Case], list[str]]:
        return sorted(self.cases.values(), key=lambda c: c.updated_at, reverse=True), []

    def get_case(self, case_id: str) -> Case:
        if case_id not in self.cases:
            raise KeyError(case_id)
        return self.cases[case_id]

    def transition(
        self,
        case_id: str,
        target: CaseState,
        event_type: EventType,
        *,
        traceparent: str,
        human_actor: bool = False,
        approval_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Case:
        self.transitions.append(
            {
                "case_id": case_id,
                "target": target,
                "event_type": event_type,
                "human_actor": human_actor,
                "approval_id": approval_id,
                "payload": payload,
            }
        )
        updated = self.cases[case_id].model_copy(
            update={"state": target, "updated_at": datetime.now(UTC) + timedelta(seconds=1)}
        )
        self.cases[case_id] = updated
        return updated


class FakeApprovalStore:
    def __init__(self) -> None:
        self.minted: list[Approval] = []

    def mint(
        self,
        *,
        case_id: str,
        action: str,
        target_state: CaseState,
        approver: str,
        traceparent: str,
    ) -> Approval:
        approval = Approval(
            approval_id=f"apr-{len(self.minted):012d}",
            case_id=case_id,
            action=action,
            target_state=target_state,
            approver=approver,
            approval_token="tok-" + "x" * 40,
            traceparent=traceparent,
        )
        self.minted.append(approval)
        return approval


class FakeIncidentStore:
    def __init__(self, incidents: dict[str, Incident]) -> None:
        self.incidents = incidents
        self.resolved_by: list[str] = []

    def list_incidents(self) -> tuple[list[Incident], list[str]]:
        return sorted(self.incidents.values(), key=lambda i: i.ts, reverse=True), []

    def get(self, incident_id: str) -> Incident:
        if incident_id not in self.incidents:
            raise KeyError(incident_id)
        return self.incidents[incident_id]

    def resolve(self, incident_id: str, *, resolved_by: str) -> Incident:
        self.resolved_by.append(resolved_by)
        resolved = self.get(incident_id).model_copy(update={"status": IncidentStatus.RESOLVED})
        self.incidents[incident_id] = resolved
        return resolved


def _wire(
    app: FastAPI,
    cases: FakeCaseStore,
    approvals: FakeApprovalStore | None = None,
    incidents: FakeIncidentStore | None = None,
) -> TestClient:
    app.dependency_overrides[get_case_store] = lambda: cases
    app.dependency_overrides[get_approval_store] = lambda: approvals or FakeApprovalStore()
    app.dependency_overrides[get_incident_store] = lambda: incidents or FakeIncidentStore({})
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def clerk_setup() -> Generator[tuple[TestClient, FakeCaseStore, FakeApprovalStore], None, None]:
    app = create_app("clerk")
    cases = FakeCaseStore({"case-p": _case("case-p")})
    approvals = FakeApprovalStore()
    client = _wire(app, cases, approvals)
    yield client, cases, approvals
    app.dependency_overrides.clear()


class TestCaseDetail:
    def test_detail_renders_determination_citation_and_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROJECT_ID", "civicnexus-hack26")
        app = create_app("reader")
        client = _wire(app, FakeCaseStore({"case-p": _case("case-p")}))
        try:
            html = client.get("/cases/case-p").text
            assert "zoning@0.2.0" in html
            assert "No employees are allowed" in html
            assert "17.44.100" in html
            assert "Verifier report" in html
            assert "traces/explorer" in html  # §8 deep link
            assert "Derived from the case record" in html
        finally:
            app.dependency_overrides.clear()

    def test_reader_shows_disabled_controls_with_iam_reason(self) -> None:
        app = create_app("reader")
        client = _wire(app, FakeCaseStore({"case-p": _case("case-p")}))
        try:
            html = client.get("/cases/case-p").text
            assert "cannot write because IAM refuses" in html
            assert "<button disabled" in html
        finally:
            app.dependency_overrides.clear()

    def test_fleet_owned_state_shows_no_buttons(self) -> None:
        app = create_app("reader")
        client = _wire(app, FakeCaseStore({"case-t": _case("case-t", state=CaseState.IN_REVIEW)}))
        try:
            html = client.get("/cases/case-t").text
            assert "the fleet owns this case" in html
            assert "<button" not in html
        finally:
            app.dependency_overrides.clear()

    def test_unknown_case_404(self) -> None:
        app = create_app("reader")
        client = _wire(app, FakeCaseStore({}))
        try:
            assert client.get("/cases/case-none").status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestClerkActions:
    def test_approve_needs_no_row_and_is_human(
        self, clerk_setup: tuple[TestClient, FakeCaseStore, FakeApprovalStore]
    ) -> None:
        client, cases, approvals = clerk_setup
        response = client.post(
            "/cases/case-p/action",
            data={"target": "APPROVED"},
            headers=_bearer("clerk@city.test"),
        )
        assert response.status_code == 303
        [t] = cases.transitions
        assert t["target"] is CaseState.APPROVED
        assert t["human_actor"] is True
        assert t["approval_id"] is None
        assert approvals.minted == []
        assert t["payload"] == {"action": "approve", "approver": "clerk@city.test"}

    def test_issue_mints_row_and_passes_its_id(
        self, clerk_setup: tuple[TestClient, FakeCaseStore, FakeApprovalStore]
    ) -> None:
        client, cases, approvals = clerk_setup
        auth = _bearer("c@x.test")
        client.post("/cases/case-p/action", data={"target": "APPROVED"}, headers=auth)
        response = client.post("/cases/case-p/action", data={"target": "ISSUED"}, headers=auth)
        assert response.status_code == 303
        [minted] = approvals.minted
        assert minted.case_id == "case-p"
        assert minted.target_state is CaseState.ISSUED
        assert minted.action == "issue"
        assert minted.approver == "c@x.test"
        assert cases.transitions[-1]["approval_id"] == minted.approval_id

    def test_illegal_target_is_409(
        self, clerk_setup: tuple[TestClient, FakeCaseStore, FakeApprovalStore]
    ) -> None:
        client, cases, _ = clerk_setup
        response = client.post(
            "/cases/case-p/action", data={"target": "ISSUED"}, headers=_bearer("c@x.test")
        )
        assert response.status_code == 409  # PENDING_HUMAN -> ISSUED is not an edge
        assert cases.transitions == []

    def test_unnamed_approver_is_400(
        self,
        clerk_setup: tuple[TestClient, FakeCaseStore, FakeApprovalStore],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
        client, cases, _ = clerk_setup
        response = client.post("/cases/case-p/action", data={"target": "APPROVED"})
        assert response.status_code == 400
        assert cases.transitions == []

    def test_form_approver_honoured_only_under_emulator(
        self,
        clerk_setup: tuple[TestClient, FakeCaseStore, FakeApprovalStore],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 2026-08-27 audit finding: the local-dev fallback must be a guard,
        # not a comment. Without the emulator marker a form-supplied name is
        # refused; with it (real local dev) it is honoured.
        client, cases, _ = clerk_setup
        monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
        refused = client.post(
            "/cases/case-p/action", data={"target": "APPROVED", "approver": "mallory@x.test"}
        )
        assert refused.status_code == 400
        assert cases.transitions == []
        monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8087")
        allowed = client.post(
            "/cases/case-p/action", data={"target": "APPROVED", "approver": "dev@local.test"}
        )
        assert allowed.status_code == 303
        assert cases.transitions[-1]["payload"] == {
            "action": "approve",
            "approver": "dev@local.test",
        }

    def test_quarantine_readmit_and_discard(self) -> None:
        app = create_app("clerk")
        cases = FakeCaseStore({"case-q": _case("case-q", state=CaseState.QUARANTINED)})
        client = _wire(app, cases)
        try:
            response = client.post(
                "/cases/case-q/action",
                data={"target": "IN_REVIEW"},
                headers=_bearer("c@x.test"),
            )
            assert response.status_code == 303
            assert cases.transitions[-1]["event_type"] is EventType.REVIEW_REQUESTED
        finally:
            app.dependency_overrides.clear()


class TestIncidents:
    def test_list_and_detail_metadata_only(self) -> None:
        app = create_app("reader")
        incidents = FakeIncidentStore({"inc-1": _incident()})
        client = _wire(app, FakeCaseStore({}), incidents=incidents)
        try:
            listing = client.get("/incidents").text
            assert "inc-1" in listing
            detail = client.get("/incidents/inc-1").text
            assert "pi_and_jailbreak" in detail
            assert "inbound_content" in detail
            # D8: the quarantine URI is inert text - never a link, no signed URL
            assert 'href="gs://' not in detail
            assert "signed" not in detail.lower() or "no download" in detail
            assert "Metadata only" in detail
        finally:
            app.dependency_overrides.clear()

    def test_reader_cannot_resolve(self) -> None:
        app = create_app("reader")
        incidents = FakeIncidentStore({"inc-1": _incident()})
        client = _wire(app, FakeCaseStore({}), incidents=incidents)
        try:
            assert client.post("/incidents/inc-1/resolve").status_code == 404
            assert incidents.resolved_by == []
        finally:
            app.dependency_overrides.clear()

    def test_clerk_resolve_records_named_human(self) -> None:
        app = create_app("clerk")
        incidents = FakeIncidentStore({"inc-1": _incident()})
        client = _wire(app, FakeCaseStore({}), incidents=incidents)
        try:
            response = client.post("/incidents/inc-1/resolve", headers=_bearer("c@x.test"))
            assert response.status_code == 303
            assert incidents.resolved_by == ["c@x.test"]
        finally:
            app.dependency_overrides.clear()

    def test_api_incidents_shape(self) -> None:
        app = create_app("reader")
        incidents = FakeIncidentStore({"inc-1": _incident()})
        client = _wire(app, FakeCaseStore({}), incidents=incidents)
        try:
            body = client.get("/api/incidents").json()
            assert [i["incident_id"] for i in body["incidents"]] == ["inc-1"]
        finally:
            app.dependency_overrides.clear()


class TestEvals:
    def test_renders_report_unedited(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        report = tmp_path / "eval-report.md"
        report.write_text("Gates: FAIL - decision_accuracy 0.750 < 0.85", encoding="utf-8")
        monkeypatch.setenv("EVAL_REPORT_PATH", str(report))
        app = create_app("reader")
        client = _wire(app, FakeCaseStore({}))
        try:
            html = client.get("/evals").text
            assert "decision_accuracy 0.750" in html  # the red gate is VISIBLE
        finally:
            app.dependency_overrides.clear()
