"""Registry-backed dynamic toolset — the hot-add mechanism (ADR-003, ratified).

On every invocation the coordinator's tool list is rebuilt from the registry:
one consult tool per **APPROVED** agent card. The approved-only filter is the
mandatory tool-poisoning defense (human ruling 2026-08-20; §6.7 threat
"lookalike/unapproved agent registered") — a card that is PENDING or
QUARANTINED never becomes a tool, so approving a new agent makes it
dispatchable on the next case with no redeploy anywhere, and quarantining one
removes it just as fast.

Remote calls use the proven ``:streamQuery`` transport (ruled 2026-08-20;
A2A-proper deferred to the Phase 6 managed-mode attempt). Registry calls carry
a Google-signed ID token for the Cloud Run leg, per the ratified auth planes.
"""

import json
import logging
import os
from collections.abc import Callable
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool

_TIMEOUT_S = 30.0


def _registry_url() -> str:
    return os.environ.get("REGISTRY_URL", "").rstrip("/")


def _id_token(audience: str) -> str:
    """Google-signed ID token for the registry's Cloud Run audience."""
    import google.auth.transport.requests
    from google.oauth2 import id_token as id_token_mod

    request = google.auth.transport.requests.Request()
    token: str = id_token_mod.fetch_id_token(request, audience)  # type: ignore[no-untyped-call]
    return token


def _fetch_via_http(capability: str | None) -> list[dict[str, Any]]:
    import httpx

    base = _registry_url()
    if not base:
        return []
    params: dict[str, str] = {"status": "APPROVED"}
    if capability:
        params["capability"] = capability
    response = httpx.get(
        f"{base}/agents",
        params=params,
        headers={"Authorization": f"Bearer {_id_token(base)}"},
        timeout=_TIMEOUT_S,
    )
    response.raise_for_status()
    cards: list[dict[str, Any]] = response.json()
    return cards


def _fetch_via_firestore(capability: str | None) -> list[dict[str, Any]]:
    """B-007 interim (human-ruled 2026-08-21): read registry_agents directly.

    The approved-only filter lives IN THE QUERY — status == APPROVED — so the
    tool-poisoning defense is identical to the HTTP path. Reverts to the
    registry service when Google's edge routes it (see ADR-003 / B-007).
    """
    from google.cloud import firestore

    # PROJECT_ID (the id, baked at deploy) first: the runtime's
    # GOOGLE_CLOUD_PROJECT holds the project NUMBER, which Firestore's
    # default-database lookup rejects (engine log, 2026-08-21).
    project = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or None
    db = firestore.Client(project=project)
    query = db.collection("registry_agents").where("status", "==", "APPROVED")
    if capability:
        query = query.where("capabilities", "array_contains", capability)
    return [card for snapshot in query.stream() if (card := snapshot.to_dict()) is not None]


def fetch_approved_cards(capability: str | None = None) -> list[dict[str, Any]]:
    """APPROVED cards only. Mode: REGISTRY_MODE=http (default) | firestore."""
    if os.environ.get("REGISTRY_MODE", "http") == "firestore":
        return _fetch_via_firestore(capability)
    return _fetch_via_http(capability)


def _consult_remote(endpoint: str, task_payload: str) -> dict[str, Any]:
    """Call a remote agent engine over raw REST :streamQuery.

    Deliberately NOT the vertexai SDK: inside the engine runtime our
    GOOGLE_CLOUD_LOCATION=global model-routing override (ADR-001 item 8)
    poisons the SDK's endpoint resolution — consults stall against the
    global endpoint and surface as 503 (isolated 2026-08-25: identical
    call succeeds via explicit regional REST as sa-caseflow, hangs via SDK
    with the override set). The regional URL here is immune to env.
    """
    import secrets

    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    from caseflow_agent.reply_parsing import last_json_object

    region = os.environ.get("RAG_LOCATION", "us-central1")
    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{endpoint}:streamQuery"
    body: Any = {
        "class_method": "stream_query",
        "input": {
            "user_id": f"coordinator-{secrets.token_hex(4)}",
            "message": task_payload,
        },
    }
    response = session.post(url, json=body, timeout=300)
    response.raise_for_status()
    events: list[dict[str, Any]] = []
    for line in response.text.splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # partial/non-JSON stream chunk
    return last_json_object(events)


def _make_consult_tool(card: dict[str, Any]) -> FunctionTool:
    """One named tool per approved card; name/doc drive the LLM's routing."""
    agent_id = str(card["agent_id"]).replace("-", "_")
    endpoint = str(card["endpoint"])
    description = str(card.get("description", ""))

    def consult(request: str) -> dict[str, Any]:
        payload = json.dumps({"task": "review", "application": json.loads(request)})
        return _consult_remote(endpoint, payload)

    consult.__name__ = f"consult_{agent_id}"
    consult.__doc__ = (
        f"Delegate the structured application (JSON string) to the approved "
        f"'{card['agent_id']}' specialist (v{card['version']}). {description} "
        f"Returns the specialist's structured finding."
    )
    return FunctionTool(consult)


class RegistryToolset(BaseToolset):
    """Rebuilds consult tools from the registry on each resolution pass."""

    def __init__(self, capability: str | None = None) -> None:
        super().__init__()
        self._capability = capability

    async def get_tools(self, readonly_context: Any = None) -> list[BaseTool]:
        try:
            cards = fetch_approved_cards(self._capability)
        except Exception:
            # Fail CLOSED: no registry answer means no remote tools this
            # turn — the fixed in-process specialists still work. Stdlib
            # logging (not libs/otel, which is outside the deployed dep set)
            # so the swallowed cause reaches Cloud Logging.
            logging.getLogger("caseflow.registry_toolset").exception(
                "registry fetch failed; failing closed with no remote tools"
            )
            return []
        return [_make_consult_tool(card) for card in cards]

    async def close(self) -> None:  # nothing persistent to release
        return None


def make_consult_callable(endpoint: str) -> Callable[[str], dict[str, Any]]:
    """Exposed for tests: the raw remote-consult callable for one endpoint."""

    def consult(request: str) -> dict[str, Any]:
        payload = json.dumps({"task": "review", "application": json.loads(request)})
        return _consult_remote(endpoint, payload)

    return consult
