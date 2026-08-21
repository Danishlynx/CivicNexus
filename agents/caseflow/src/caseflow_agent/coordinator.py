"""Coordinator: routes casework tasks to specialist agents (§3.1).

Specialists are attached as explicit ``AgentTool``s, not ``sub_agents``
(ADR-004, human-ratified 2026-08-21). Under the Agent Engine workflow
runtime, ``sub_agents`` become nested nodes whose every final text is
hard-validated against that agent's ``output_schema``
(``workflow/_llm_agent_wrapper.py::process_llm_agent_output``) — which
nondeterministically rejected the coordinator's multi-capability composition
(B-009). An explicit ``AgentTool`` runs its agent in a private Runner
instead: the specialist's schema binds only the specialist's own reply
inside the tool call, and the coordinator (no output schema) always owns
the final composition.
"""

import json
import os
from typing import Any

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types

from caseflow_agent.intake import intake_agent
from caseflow_agent.registry_toolset import RegistryToolset
from caseflow_agent.zoning import zoning_agent


def _specialist_request(agent_name: str, original: str) -> str | None:
    """Baseline-parity payload, extracted in code (never LLM-retyped).

    The measured-80% wiring fed specialists the BARE application — intake
    got the raw text, zoning got the application dict (with the
    verifier_critique injected as a field on retries, which zoning's
    instruction explicitly handles). Handing zoning the whole task envelope
    instead measurably degraded borderline decisions (B-009 final runs).
    Returns None when the original message is unusable — caller falls back
    to the LLM-typed request.
    """
    try:
        message = json.loads(original)
        application = message.get("application")
        if application is None:
            return None
        if agent_name == "intake":
            return application if isinstance(application, str) else json.dumps(application)
        payload = dict(application) if isinstance(application, dict) else {"data": application}
        if "verifier_critique" in message:
            payload["verifier_critique"] = message["verifier_critique"]
        return json.dumps(payload)
    except Exception:
        return None


class SafeAgentTool(AgentTool):
    """AgentTool whose failures return to the model instead of raising.

    With no on_tool_error callbacks, a raised tool exception aborts the whole
    (billed) invocation. Mirror the framework's own single-turn wrapper
    pattern: catch, and hand the model a structured error it can react to.
    """

    async def run_async(self, *, args: dict[str, Any], tool_context: Any) -> Any:
        # Deterministic INPUT leg (B-009 final form): extract the
        # baseline-parity payload from the ORIGINAL message in code. The
        # LLM's arg is only the trigger; code owns what flows through.
        try:
            content = tool_context.user_content
            original = "".join(p.text or "" for p in content.parts) if content else ""
            request = _specialist_request(self.agent.name, original)
            if request:
                args = {"request": request}
        except Exception:
            pass
        try:
            result = await super().run_async(args=args, tool_context=tool_context)
        except Exception as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
        name = self.agent.name
        if isinstance(result, dict) and "error" not in result:
            plain = json.loads(json.dumps(result))
            tool_context.state[f"temp:civicnexus:finding:{name}"] = plain
            return plain
        detail = result.get("error") if isinstance(result, dict) else str(result)
        tool_context.state[f"temp:civicnexus:error:{name}"] = detail
        return result


_FINDING_PREFIX = "temp:civicnexus:finding:"
_ERROR_PREFIX = "temp:civicnexus:error:"


def compose_reply(callback_context: Any) -> genai_types.Content | None:
    """Deterministic final reply: the LLM routes, this code composes.

    Fixes the measured echo-infidelity regression (B-009 update): findings
    reach the wire byte-exact from the specialists' validated dicts, never
    re-typed by the model. Appended as the LAST content event — every repo
    client takes the last JSON object, so this is the authoritative reply.

    Total by design: a raised callback aborts the whole billed invocation,
    so every failure path returns parseable fail-closed JSON instead.
    Valid ONLY while the coordinator is the ROOT agent (chat mode): as a
    single_turn workflow node this callback's role='model' Content would
    collide with the node's single-output rule (offline repro in ADR-004
    addendum 2). Known skip mode: if the flow sets end_invocation mid-run
    (auth interrupts, plugin aborts) the callback never fires and the raw
    LLM text stands — fail-closed at the consumer's validator.
    """
    try:
        content = callback_context.user_content
        raw = "".join(p.text or "" for p in content.parts) if content and content.parts else ""
        message = json.loads(raw)
        state = callback_context.state.to_dict()
        findings = {
            k[len(_FINDING_PREFIX) :]: v for k, v in state.items() if k.startswith(_FINDING_PREFIX)
        }
        errors = {
            k[len(_ERROR_PREFIX) :]: v for k, v in state.items() if k.startswith(_ERROR_PREFIX)
        }
        task = message.get("task")
        reply: dict[str, Any]
        if task == "intake":
            reply = findings.get(
                "intake", {"error": errors.get("intake", "intake finding unavailable")}
            )
        elif task == "review":
            requested = [str(c) for c in (message.get("capabilities") or ["zoning"])]
            if requested == ["zoning"]:
                # Bare dict, no envelope: the graders validate extra="forbid".
                reply = findings.get(
                    "zoning", {"error": errors.get("zoning", "zoning finding unavailable")}
                )
            else:
                reply = {
                    "findings": [
                        {"capability": cap, "finding": findings[cap]}
                        for cap in requested
                        if cap in findings
                    ]
                }
                errored = [
                    {"capability": cap, "error": errors[cap]}
                    for cap in requested
                    if cap not in findings and cap in errors
                ]
                if errored:
                    reply["errors"] = errored
                # Key OMITTED when nothing is missing (demo asserts on raw
                # substring); errored specialists are NOT "missing".
                missing = [c for c in requested if c not in findings and c not in errors]
                if missing:
                    reply["missing_capability"] = missing[0]
        else:
            reply = {"error": "unknown task"}
    except Exception as exc:
        reply = {"error": f"composer: {type(exc).__name__}: {exc}"}
    return genai_types.Content(
        role="model", parts=[genai_types.Part.from_text(text=json.dumps(reply))]
    )


coordinator = Agent(
    name="coordinator",
    model=os.environ.get("MODEL_ID", "gemini-3.5-flash"),
    generate_content_config=genai_types.GenerateContentConfig(temperature=0.0),
    description="Plans and delegates permit-case work to specialist agents.",
    instruction=(
        'You coordinate permit casework. The user message is JSON with a "task" '
        "field.\n"
        '- task "intake": call the intake tool exactly once, passing the raw '
        "application text as the request; then return the intake tool's JSON "
        "result verbatim.\n"
        '- task "review": the message contains the structured application and a '
        '"capabilities" list naming the reviews this permit type requires. For '
        'the "zoning" capability, call the zoning tool exactly once, passing '
        "the structured application JSON as the request. For any OTHER "
        "capability, use the matching consult_<agent> tool if one is available "
        "- these tools are the registry's currently APPROVED specialists. If a "
        "required capability has no matching specialist, note it in the output "
        'as {"missing_capability": "<name>"} alongside the findings you did '
        "obtain.\n"
        "Every tool call's request must be the application data itself - never "
        "pass your own draft reply or another specialist's finding into a "
        "tool. One exception: if the message contains a verifier_critique "
        "field, include it verbatim in the zoning tool request alongside the "
        "application JSON - the zoning reviewer needs it to correct its "
        "finding.\n"
        "When a review requires multiple capabilities, collect every "
        'specialist\'s finding and reply with JSON: {"findings": '
        '[{"capability": ..., "finding": <specialist JSON>}]}. For a single '
        "zoning-only review, return the zoning tool's JSON verbatim.\n"
        "Return ONLY JSON - no commentary, no code fences. If the task field "
        'is missing or unknown, reply with {"error": "unknown task"}.'
    ),
    tools=[SafeAgentTool(intake_agent), SafeAgentTool(zoning_agent), RegistryToolset()],
    after_agent_callback=compose_reply,
)
