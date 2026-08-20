"""Registry HTTP surface.

Authentication is enforced by the platform: the Cloud Run service deploys
with ``--no-allow-unauthenticated``, so only principals holding
``roles/run.invoker`` reach this app at all (deny-by-default; this is the
ratified ID-token + run.invoker pattern with Google doing the verification).
The app additionally reads the platform-verified caller identity from the
``Authorization`` context for audit attribution — it never does its own token
cryptography.

LOCAL DEV AUTH PATH (explicit, per Working Agreement — dev never routes
around security silently): run locally via ``uvicorn registry.app:app`` with
the Firestore emulator. There is NO platform in front of you locally, so
every request is anonymous by construction: ``caller_identity`` returns ""
and audit lines attribute to "system". This is acceptable ONLY against the
emulator; never point a locally-run registry at production Firestore.
"""

import base64
import binascii
import json
import os
from typing import Any

from civicnexus.contracts import AgentCard, AgentStatus
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from registry.store import (
    DuplicateCardError,
    LifecycleError,
    RegistryStore,
    UnknownCardError,
)

app = FastAPI(title="civicnexus-registry", version="0.1.0")

_store: RegistryStore | None = None


def get_store() -> RegistryStore:
    global _store
    if _store is None:
        from google.cloud import firestore

        _store = RegistryStore(firestore.Client(project=os.environ.get("PROJECT_ID")))
    return _store


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
            email = claims.get("email", "")
            return str(email)
        except (IndexError, ValueError, binascii.Error):
            return ""
    return ""


class StatusChange(BaseModel):
    """Body for approve/quarantine calls."""

    model_config = ConfigDict(extra="forbid")

    actor: str = ""
    human_actor: bool = True


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agents", status_code=201)
def register(card: AgentCard, store: RegistryStore = Depends(get_store)) -> AgentCard:
    try:
        return store.register(card)
    except DuplicateCardError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/agents")
def find(
    capability: str | None = None,
    status: AgentStatus | None = None,
    store: RegistryStore = Depends(get_store),
) -> list[AgentCard]:
    return store.find(capability=capability, status=status)


@app.get("/agents/{agent_id}/{version}")
def get_card(agent_id: str, version: str, store: RegistryStore = Depends(get_store)) -> AgentCard:
    try:
        return store.get(agent_id, version)
    except UnknownCardError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _change(
    agent_id: str,
    version: str,
    target: AgentStatus,
    body: StatusChange,
    request: Request,
    store: RegistryStore,
) -> AgentCard:
    actor = body.actor or caller_identity(request)
    try:
        return store.change_status(
            agent_id, version, target, actor=actor, human_actor=body.human_actor
        )
    except UnknownCardError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LifecycleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/agents/{agent_id}/{version}/approve")
def approve(
    agent_id: str,
    version: str,
    body: StatusChange,
    request: Request,
    store: RegistryStore = Depends(get_store),
) -> AgentCard:
    return _change(agent_id, version, AgentStatus.APPROVED, body, request, store)


@app.post("/agents/{agent_id}/{version}/quarantine")
def quarantine(
    agent_id: str,
    version: str,
    body: StatusChange,
    request: Request,
    store: RegistryStore = Depends(get_store),
) -> AgentCard:
    return _change(agent_id, version, AgentStatus.QUARANTINED, body, request, store)
