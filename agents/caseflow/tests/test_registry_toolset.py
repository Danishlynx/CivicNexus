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
    monkeypatch.delenv("REGISTRY_URL", raising=False)
    assert registry_toolset.fetch_approved_cards() == []


def test_toolset_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(capability: str | None = None) -> list[dict[str, Any]]:
        raise RuntimeError("registry unreachable")

    monkeypatch.setattr(registry_toolset, "fetch_approved_cards", boom)
    tools = asyncio.run(RegistryToolset().get_tools())
    assert tools == []


def test_toolset_builds_named_tools(monkeypatch: pytest.MonkeyPatch) -> None:
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
