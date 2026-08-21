"""Deterministic composer tests (ADR-004 addendum 2): the LLM routes, code
composes — these pin every reply-shape contract the graders and demo assert."""

import json
from types import SimpleNamespace
from typing import Any

from caseflow_agent.coordinator import compose_reply, coordinator

ZONING = {"outcome": "approve", "citations": [{"chunk_id": "17.44.100", "quote": "§ exact"}]}
TREE = {"outcome": "deny", "citations": [{"chunk_id": "17.44.057", "quote": "oak—tree"}]}
INTAKE = {"applicant_name": "Synthetic Rosa", "complete": True, "missing_items": []}


def _ctx(message: dict[str, Any], state: dict[str, Any]) -> SimpleNamespace:
    part = SimpleNamespace(text=json.dumps(message))
    return SimpleNamespace(
        user_content=SimpleNamespace(parts=[part]),
        state=SimpleNamespace(to_dict=lambda: state),
    )


def _reply(message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    content = compose_reply(_ctx(message, state))
    assert content is not None and content.parts
    parsed: dict[str, Any] = json.loads(content.parts[0].text or "")
    return parsed


def test_composer_is_wired() -> None:
    assert coordinator.after_agent_callback is compose_reply


def test_intake_verbatim() -> None:
    reply = _reply({"task": "intake"}, {"temp:civicnexus:finding:intake": INTAKE})
    assert reply == INTAKE


def test_zoning_only_bare_dict_byte_exact() -> None:
    reply = _reply(
        {"task": "review", "capabilities": ["zoning"]},
        {"temp:civicnexus:finding:zoning": ZONING},
    )
    assert reply == ZONING  # no envelope, quotes byte-exact incl. non-ASCII


def test_capabilities_absent_defaults_to_zoning() -> None:
    reply = _reply(
        {"task": "review", "verifier_critique": "quote 2 not verbatim"},
        {"temp:civicnexus:finding:zoning": ZONING},
    )
    assert reply == ZONING


def test_multi_capability_envelope_and_missing_omitted() -> None:
    reply = _reply(
        {"task": "review", "capabilities": ["zoning", "tree_preservation"]},
        {
            "temp:civicnexus:finding:zoning": ZONING,
            "temp:civicnexus:finding:tree_preservation": TREE,
        },
    )
    assert reply["findings"] == [
        {"capability": "zoning", "finding": ZONING},
        {"capability": "tree_preservation", "finding": TREE},
    ]
    assert "missing_capability" not in json.dumps(reply)


def test_missing_specialist_named() -> None:
    reply = _reply(
        {"task": "review", "capabilities": ["zoning", "tree_preservation"]},
        {"temp:civicnexus:finding:zoning": ZONING},
    )
    assert reply["missing_capability"] == "tree_preservation"


def test_errored_specialist_is_not_missing_and_not_a_finding() -> None:
    reply = _reply(
        {"task": "review", "capabilities": ["zoning", "tree_preservation"]},
        {
            "temp:civicnexus:finding:zoning": ZONING,
            "temp:civicnexus:error:tree_preservation": "TransportError: boom",
        },
    )
    assert reply["errors"] == [{"capability": "tree_preservation", "error": "TransportError: boom"}]
    assert "missing_capability" not in reply
    assert all(f["capability"] != "tree_preservation" for f in reply["findings"])


def test_unknown_task_and_totality() -> None:
    assert _reply({"task": "dance"}, {}) == {"error": "unknown task"}
    broken = SimpleNamespace(user_content=None, state=SimpleNamespace(to_dict=dict))
    content = compose_reply(broken)
    assert content is not None and content.parts
    assert "error" in json.loads(content.parts[0].text or "")


def test_zoning_finding_unavailable_fails_closed() -> None:
    reply = _reply({"task": "review", "capabilities": ["zoning"]}, {})
    assert reply == {"error": "zoning finding unavailable"}
