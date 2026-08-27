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
from pathlib import Path
from typing import Any

from civicnexus.contracts import Actor, EventEnvelope
from civicnexus.otel import get_logger
from civicnexus.tools import ApprovalStore, CaseStore, IncidentStore
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

_log = get_logger("console")

_READER = "reader"
_CLERK = "clerk"

_ACTOR = Actor(agent_id="console", agent_version="0.1.0")

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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


read_router = APIRouter()

#: Clerk-only routes (mounted ONLY when CONSOLE_MODE=clerk — in reader mode
#: they do not exist, so a write attempt on the public service is a 404, not a
#: 403 with a tempting handler behind it). Populated in the action step.
clerk_router = APIRouter()


@read_router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@read_router.get("/", response_class=HTMLResponse)
def queue(request: Request, cases: CaseStore = Depends(get_case_store)) -> HTMLResponse:
    listed, invalid = cases.list_cases()
    return _templates.TemplateResponse(
        request,
        "queue.html",
        {
            "mode": request.app.state.mode,
            "cases": listed,
            "invalid_count": len(invalid),
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


def create_app(mode: str | None = None) -> FastAPI:
    """Build the app for one exposure. ``mode=None`` reads CONSOLE_MODE."""
    resolved = resolve_mode(mode if mode is not None else os.environ.get("CONSOLE_MODE"))
    application = FastAPI(title="civicnexus-console", version="0.1.0")
    application.state.mode = resolved
    application.include_router(read_router)
    if resolved == _CLERK:
        application.include_router(clerk_router)
    return application


app = create_app()
