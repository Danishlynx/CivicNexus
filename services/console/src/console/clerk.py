"""Clerk-only routes — imported and mounted ONLY under ``CONSOLE_MODE=clerk``.

This module is the single place in the console permitted to read the
``Authorization`` context: on the clerk service the platform (Cloud Run IAM,
``roles/run.invoker`` limited to named principals) has already verified the
token, so decoding its payload for audit attribution is sound — the exact
reasoning ratified for the registry. The public reader NEVER imports this
module, so no identity-trusting path exists there at all (ADR-007 D2/D13; a
grep test enforces the confinement).

Every write goes through ``CaseStore`` / ``ApprovalStore`` / ``IncidentStore``
— this module holds no Firestore handle.
"""

import base64
import binascii
import json
import os
import uuid
from typing import Any

from civicnexus.contracts import CaseState
from civicnexus.tools import ApprovalStore, CaseStore, IncidentStore, TransitionError
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from console.actions import clerk_actions
from console.app import get_approval_store, get_case_store, get_incident_store

clerk_router = APIRouter()


def caller_identity(request: Request) -> str:
    """Best-effort caller email from the platform-verified JWT (audit only).

    Cloud Run has already verified the token before the request reaches us;
    this decodes the payload for attribution without re-verifying signatures.
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = auth.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            claims: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload))
            return str(claims.get("email", ""))
        except (IndexError, ValueError, binascii.Error):
            return ""
    return ""


def _fresh_traceparent() -> str:
    return f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"


def _named_human(request: Request, form_fallback: str) -> str:
    """The audited identity, in strict preference order.

    1. The forwarded token's email claim — kept first so that if the platform
       ever forwards a caller token, it wins. MEASURED 2026-08-28: Cloud Run
       validates and CONSUMES the Authorization credential; the container
       receives no decodable caller token (tested with Authorization alone
       and with the X-Serverless-Authorization dual-header pattern).
    2. ``CLERK_SOLE_INVOKER`` — the platform truth this deployment actually
       provides: the clerk service's ``run.invoker`` binding admits EXACTLY
       ONE named human, so any request reaching this code was made by that
       principal. The env var only restates who IAM already admits, and
       ``verify_phase6`` asserts the binding is exactly that one member, so
       this assumption is pinned, not hoped. Set only on the clerk service.
    3. The form field, ONLY against the local emulator (no platform locally;
       2026-08-27 audit finding: an unenforced comment is not a guard).
    """
    named = caller_identity(request)
    if not named:
        named = os.environ.get("CLERK_SOLE_INVOKER", "").strip()
    if not named and os.environ.get("FIRESTORE_EMULATOR_HOST"):
        named = form_fallback.strip()
    return named


@clerk_router.post("/cases/{case_id}/action")
def act(
    case_id: str,
    request: Request,
    target: str = Form(...),
    approver: str = Form(""),
    cases: CaseStore = Depends(get_case_store),
    approvals: ApprovalStore = Depends(get_approval_store),
) -> RedirectResponse:
    """One clerk decision: derive legality from the contract, mint the
    approvals row where §4 demands one, transition through the single writer."""
    try:
        case = cases.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        target_state = CaseState(target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"unknown target state {target!r}") from exc

    action = next((a for a in clerk_actions(case.state) if a.target is target_state), None)
    if action is None:
        raise HTTPException(
            status_code=409,
            detail=f"{target_state.value} is not a clerk action from {case.state.value}",
        )

    named = _named_human(request, approver)
    if not named:
        raise HTTPException(status_code=400, detail="a named human approver is required")

    traceparent = _fresh_traceparent()
    approval_id: str | None = None
    if action.needs_approval_row:
        # Minted before the transition; if the transition is then refused the
        # row remains as an append-only record of human intent, which is the
        # honest ordering (an approval without effect beats an effect without
        # approval).
        row = approvals.mint(
            case_id=case_id,
            action=action.slug,
            target_state=target_state,
            approver=named,
            traceparent=traceparent,
        )
        approval_id = row.approval_id

    try:
        cases.transition(
            case_id,
            target_state,
            action.event_type,
            traceparent=traceparent,
            human_actor=True,
            approval_id=approval_id,
            payload={"action": action.slug, "approver": named},
        )
    except TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@clerk_router.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    request: Request,
    approver: str = Form(""),
    incidents: IncidentStore = Depends(get_incident_store),
) -> RedirectResponse:
    named = _named_human(request, approver)
    if not named:
        raise HTTPException(status_code=400, detail="a named human is required to resolve")
    try:
        incidents.resolve(incident_id, resolved_by=named)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(f"/incidents/{incident_id}", status_code=303)
