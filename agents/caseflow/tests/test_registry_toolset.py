"""Tests for the hot-add toolset: approved-only filter, naming, fail-closed."""

import asyncio
from typing import Any

import pytest
from caseflow_agent import registry_toolset
from caseflow_agent.registry_toolset import RegistryToolset, _make_consult_tool
from caseflow_agent.reply_parsing import last_json_object

CARD = {
    "agent_id": "tree-preservation",
    "version": "1.0.0",
    "description": "Reviews protected-tree impact.",
    "capabilities": ["tree_preservation"],
    "endpoint": "projects/p/locations/l/reasoningEngines/42",
    "status": "APPROVED",
}


def test_fetch_requests_approved_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the mode: REGISTRY_MODE=firestore is the B-007 interim and is
    # routinely exported for demos, so inheriting it would silently route this
    # HTTP-path test down the Firestore branch (an F14-class ambient-env trap).
    monkeypatch.delenv("REGISTRY_MODE", raising=False)
    captured: dict[str, Any] = {}

    class _Resp:
        def raise_for_status(self) -> None: ...
        def json(self) -> list[dict[str, Any]]:
            return [CARD]

    def fake_get(
        url: str, *, params: dict[str, str], headers: dict[str, str], timeout: float
    ) -> _Resp:
        captured["url"] = url
        captured["params"] = params
        return _Resp()

    import httpx

    monkeypatch.setenv("REGISTRY_URL", "https://registry.example.test")
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(registry_toolset, "_id_token", lambda aud: "tok")

    cards = registry_toolset.fetch_approved_cards("tree_preservation")
    assert cards == [CARD]
    # The mandatory tool-poisoning defense: the filter is in the REQUEST.
    assert captured["params"]["status"] == "APPROVED"
    assert captured["params"]["capability"] == "tree_preservation"
    assert captured["url"].endswith("/agents")


def test_no_registry_url_means_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the mode: REGISTRY_MODE=firestore is the B-007 interim and is
    # routinely exported for demos, so inheriting it would silently route this
    # HTTP-path test down the Firestore branch (an F14-class ambient-env trap).
    monkeypatch.delenv("REGISTRY_MODE", raising=False)
    monkeypatch.delenv("REGISTRY_URL", raising=False)
    assert registry_toolset.fetch_approved_cards() == []


def test_firestore_mode_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """REGISTRY_MODE=firestore routes to the interim path, never HTTP."""
    called: dict[str, Any] = {}

    def fake_firestore(capability: str | None) -> list[dict[str, Any]]:
        called["capability"] = capability
        return [CARD]

    def no_http(capability: str | None) -> list[dict[str, Any]]:
        raise AssertionError("HTTP path must not run in firestore mode")

    monkeypatch.setenv("REGISTRY_MODE", "firestore")
    monkeypatch.setattr(registry_toolset, "_fetch_via_firestore", fake_firestore)
    monkeypatch.setattr(registry_toolset, "_fetch_via_http", no_http)

    assert registry_toolset.fetch_approved_cards("tree_preservation") == [CARD]
    assert called["capability"] == "tree_preservation"


def test_firestore_query_filters_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool-poisoning defense holds in the interim path: the status filter
    is part of the Firestore QUERY, not post-hoc filtering in Python."""
    filters: list[tuple[str, str, Any]] = []

    class _Snapshot:
        def to_dict(self) -> dict[str, Any]:
            return CARD

    class _Query:
        def where(self, field: str, op: str, value: Any) -> "_Query":
            filters.append((field, op, value))
            return self

        def stream(self) -> list[_Snapshot]:
            return [_Snapshot()]

    class _Client:
        def __init__(self, project: str | None = None) -> None: ...
        def collection(self, name: str) -> _Query:
            filters.append(("__collection__", "==", name))
            return _Query()

    import google.cloud.firestore as firestore_mod

    monkeypatch.setattr(firestore_mod, "Client", _Client)

    cards = registry_toolset._fetch_via_firestore("tree_preservation")
    assert cards == [CARD]
    assert ("__collection__", "==", "registry_agents") in filters
    assert ("status", "==", "APPROVED") in filters
    assert ("capabilities", "array_contains", "tree_preservation") in filters


def test_toolset_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the mode: REGISTRY_MODE=firestore is the B-007 interim and is
    # routinely exported for demos, so inheriting it would silently route this
    # HTTP-path test down the Firestore branch (an F14-class ambient-env trap).
    monkeypatch.delenv("REGISTRY_MODE", raising=False)

    def boom(capability: str | None = None) -> list[dict[str, Any]]:
        raise RuntimeError("registry unreachable")

    monkeypatch.setattr(registry_toolset, "fetch_approved_cards", boom)
    tools = asyncio.run(RegistryToolset().get_tools())
    assert tools == []


def test_toolset_builds_named_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the mode: REGISTRY_MODE=firestore is the B-007 interim and is
    # routinely exported for demos, so inheriting it would silently route this
    # HTTP-path test down the Firestore branch (an F14-class ambient-env trap).
    monkeypatch.delenv("REGISTRY_MODE", raising=False)
    monkeypatch.setattr(registry_toolset, "fetch_approved_cards", lambda capability=None: [CARD])
    tools = asyncio.run(RegistryToolset().get_tools())
    assert len(tools) == 1
    assert tools[0].name == "consult_tree_preservation"


def test_consult_tool_metadata() -> None:
    tool = _make_consult_tool(CARD)
    assert tool.name == "consult_tree_preservation"
    assert "tree-preservation" in (tool.description or "")
    assert "1.0.0" in (tool.description or "")


def test_last_json_object_prefers_final() -> None:
    events = [
        {"content": {"parts": [{"text": "thinking"}]}},
        {"content": {"parts": [{"text": '{"outcome": "approve"}'}]}},
    ]
    assert last_json_object(events) == {"outcome": "approve"}


def test_last_json_object_raises_on_silence() -> None:
    with pytest.raises(RuntimeError, match="no text"):
        last_json_object([{"author": "x"}])
