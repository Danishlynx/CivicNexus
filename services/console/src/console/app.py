"""Console HTTP surface (ADR-007 D1/D2/D5).

One FastAPI package, served as TWO Cloud Run services from the same image:

- ``CONSOLE_MODE=reader`` (the DEFAULT, so a misconfiguration fails closed):
  the public service. Write routes are NOT mounted, the event publisher is a
  stub that refuses, and the service account holds read-only Firestore access
  and nothing else — the exposure is bounded by IAM, not by code politeness
  (D13). No caller-identity decoding exists on this path.
- ``CONSOLE_MODE=clerk``: the private, IAM-gated service the named clerk uses.
  It writes exclusively through ``CaseStore`` / ``ApprovalStore`` /
  ``IncidentStore`` — the single-writer model imported in-process (D7); this
  module never touches a Firestore document handle itself, and a test greps
  its source to keep that true.

Content rules (D8): log ids only — never a case dict, an applicant object, or
a request body. The incident view renders metadata only.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from civicnexus.contracts import Actor, Case, CaseState, EventEnvelope, Incident
from civicnexus.otel import get_logger
from civicnexus.tools import ApprovalStore, CaseStore, IncidentStore
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from console.actions import clerk_actions, fleet_owns

_log = get_logger("console")

_READER = "reader"
_CLERK = "clerk"

_ACTOR = Actor(agent_id="console", agent_version="0.1.0")

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

#: Humanized status labels — raw enum values never reach a reader's eye; the
#: machine value stays present in the class attribute for tooling and tests.
_STATUS_LABELS = {
    "RECEIVED": "Received",
    "TRIAGED": "Triaged",
    "INCOMPLETE_AWAITING_APPLICANT": "Awaiting applicant",
    "IN_REVIEW": "In review",
    "VERIFICATION_FAILED": "Verification failed",
    "PAUSED_BUDGET": "Budget paused",
    "PENDING_HUMAN": "Pending human review",
    "APPROVED": "Approved",
    "DENIED": "Denied",
    "INFO_REQUESTED": "Info requested",
    "ISSUED": "Issued",
    "QUARANTINED": "Quarantined",
    "CLOSED": "Closed",
    "OPEN": "Open",
    "RESOLVED": "Resolved",
    "MATCH_FOUND": "Match found",
    "NO_MATCH_FOUND": "No match",
}


def _status_label(value: str) -> str:
    return _STATUS_LABELS.get(value, value.replace("_", " ").capitalize())


_templates.env.filters["status_label"] = _status_label


def resolve_mode(raw: str | None) -> str:
    """Map the CONSOLE_MODE env var to a mode, failing CLOSED to reader."""
    if raw == _CLERK:
        return _CLERK
    if raw not in (None, "", _READER):
        _log.warning(f"unrecognised CONSOLE_MODE {raw!r}; serving as reader (fail closed)")
    return _READER


class RefusingPublisher:
    """Reader-mode publisher: the public service holds no publish permission,
    and its code refuses before IAM even gets asked (defence in depth, D13)."""

    def publish(self, envelope: EventEnvelope) -> str:
        raise RuntimeError("console reader mode cannot publish events")


_case_store: CaseStore | None = None
_incident_store: IncidentStore | None = None
_approval_store: ApprovalStore | None = None
_inbox_store: Any = None


def _db() -> Any:
    from google.cloud import firestore

    return firestore.Client(project=os.environ.get("PROJECT_ID"))


def get_case_store(request: Request) -> CaseStore:
    global _case_store
    if _case_store is None:
        db = _db()
        mode = str(request.app.state.mode)
        if mode == _CLERK:
            from civicnexus.tools import EventPublisher

            publisher: Any = EventPublisher(os.environ["PROJECT_ID"])
        else:
            publisher = RefusingPublisher()
        _case_store = CaseStore(db, publisher, _ACTOR, approvals=ApprovalStore(db))
    return _case_store


def get_incident_store() -> IncidentStore:
    global _incident_store
    if _incident_store is None:
        _incident_store = IncidentStore(_db())
    return _incident_store


def get_approval_store() -> ApprovalStore:
    global _approval_store
    if _approval_store is None:
        _approval_store = ApprovalStore(_db())
    return _approval_store


def get_inbox_store() -> Any:
    from civicnexus.tools import InboxStore

    global _inbox_store
    if _inbox_store is None:
        _inbox_store = InboxStore(_db())
    return _inbox_store


read_router = APIRouter()


@read_router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness. Deliberately NOT ``/healthz``: Google's frontend intercepts
    that literal path on run.app and answers its own 404 before the container
    is ever consulted (measured 2026-08-28; also explains B-007's registry
    "/healthz 404s on the deployed revision" note — it was never staleness)."""
    return {"status": "ok"}


@read_router.get("/", response_class=HTMLResponse)
def queue(
    request: Request,
    cases: CaseStore = Depends(get_case_store),
    q: str = "",
    state: str = "",
    limit: int = 50,
) -> HTMLResponse:
    """The queue, designed to stay calm at volume: text search, state filter,
    and bounded sections with explicit shown-of-total counts, so a clerk
    facing 10,000 cases still sees an operable page (2026-08-28 UX ruling)."""
    listed, invalid = cases.list_cases()
    total = len(listed)
    needle = q.strip().lower()
    if needle:
        listed = [
            c
            for c in listed
            if needle in c.case_id.lower()
            or needle in c.applicant.name.lower()
            or needle in c.permit_type.lower()
        ]
    if state:
        listed = [c for c in listed if c.state.value == state]
    limit = max(1, min(limit, 10_000))
    return _templates.TemplateResponse(
        request,
        "queue.html",
        {
            "mode": request.app.state.mode,
            "cases": listed,
            "total": total,
            "invalid_count": len(invalid),
            "q": q,
            "state": state,
            "limit": limit,
            "all_states": [s.value for s in CaseState],
            "now": datetime.now(UTC),
        },
    )


@read_router.get("/api/cases")
def api_cases(cases: CaseStore = Depends(get_case_store)) -> JSONResponse:
    listed, invalid = cases.list_cases()
    return JSONResponse(
        {
            "cases": [c.model_dump(mode="json") for c in listed],
            "excluded_invalid_ids": invalid,
        }
    )


def _trace_url(trace_id: str) -> str | None:
    """Cloud Trace explorer deep link (§8) — URL shape live-verified at the
    Phase 0 gate (clicked through by the human, recorded in PROGRESS)."""
    project = os.environ.get("PROJECT_ID", "")
    if not trace_id or not project:
        return None
    return (
        "https://console.cloud.google.com/traces/explorer"
        f";traceId={trace_id};duration=PT1H?project={project}"
    )


def _derived_feed(case: Case, case_incidents: list[Incident]) -> list[tuple[datetime, str]]:
    """Per-case timeline DERIVED from the case record and its incidents —
    not a replay of the §5 event stream, which has no persistent subscriber
    (ADR-007 D5 rule 2). The template labels it as derived."""
    entries: list[tuple[datetime, str]] = [(case.created_at, "Case received")]
    for timer in case.timers:
        entries.append((timer.fires_at, f"Timer {timer.timer_id} fires: {timer.reason}"))
    for incident in case_incidents:
        entries.append(
            (incident.ts, f"Incident {incident.incident_id} ({incident.kind.value}) raised")
        )
    entries.append((case.updated_at, f"Last transition, now {case.state.value}"))
    entries.sort(key=lambda e: e[0])
    return entries


@read_router.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(
    case_id: str,
    request: Request,
    cases: CaseStore = Depends(get_case_store),
    incidents: IncidentStore = Depends(get_incident_store),
) -> HTMLResponse:
    try:
        case = cases.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        # Honest failure, scoped to this page: the queue stays up (D5).
        raise HTTPException(
            status_code=500, detail=f"case document {case_id} failed contract validation"
        ) from exc
    listed_incidents, _ = incidents.list_incidents()
    case_incidents = [i for i in listed_incidents if i.case_id == case_id]
    return _templates.TemplateResponse(
        request,
        "case.html",
        {
            "mode": request.app.state.mode,
            "case": case,
            "actions": clerk_actions(case.state),
            "fleet_owns": fleet_owns(case.state),
            "feed": _derived_feed(case, case_incidents),
            "case_incidents": case_incidents,
            "trace_url": _trace_url(case.trace_id),
        },
    )


@read_router.get("/incidents", response_class=HTMLResponse)
def incident_list(
    request: Request, incidents: IncidentStore = Depends(get_incident_store)
) -> HTMLResponse:
    listed, invalid = incidents.list_incidents()
    return _templates.TemplateResponse(
        request,
        "incidents.html",
        {"mode": request.app.state.mode, "incidents": listed, "invalid_count": len(invalid)},
    )


@read_router.get("/incidents/{incident_id}", response_class=HTMLResponse)
def incident_detail(
    incident_id: str,
    request: Request,
    incidents: IncidentStore = Depends(get_incident_store),
) -> HTMLResponse:
    try:
        incident = incidents.get(incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _templates.TemplateResponse(
        request,
        "incident.html",
        {"mode": request.app.state.mode, "incident": incident},
    )


@read_router.get("/api/incidents")
def api_incidents(incidents: IncidentStore = Depends(get_incident_store)) -> JSONResponse:
    listed, invalid = incidents.list_incidents()
    return JSONResponse(
        {
            "incidents": [i.model_dump(mode="json") for i in listed],
            "excluded_invalid_ids": invalid,
        }
    )


@read_router.get("/evals", response_class=HTMLResponse)
def evals(request: Request) -> HTMLResponse:
    """Renders docs/eval-report.md UNEDITED, failing gate visible (B-006
    honesty on the record). No Looker Studio dashboard was ever built."""
    report_path = Path(os.environ.get("EVAL_REPORT_PATH", "docs/eval-report.md"))
    report = (
        report_path.read_text(encoding="utf-8")
        if report_path.exists()
        else "eval report not present in this image"
    )
    return _templates.TemplateResponse(
        request,
        "evals.html",
        {"mode": request.app.state.mode, "report": report},
    )


def create_app(mode: str | None = None) -> FastAPI:
    """Build the app for one exposure. ``mode=None`` reads CONSOLE_MODE."""
    resolved = resolve_mode(mode if mode is not None else os.environ.get("CONSOLE_MODE"))
    application = FastAPI(title="civicnexus-console", version="0.1.0")
    application.state.mode = resolved
    if resolved == _CLERK:
        # Imported ONLY here: in reader mode the clerk module (the sole
        # holder of identity decoding) is never even imported (D2).
        # Mounted BEFORE the read routes so the literal /cases/new is not
        # swallowed by the /cases/{case_id} path parameter.
        from console.clerk import clerk_router

        application.include_router(clerk_router)
    application.include_router(read_router)
    return application


app = create_app()
