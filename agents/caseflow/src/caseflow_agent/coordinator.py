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

import os
from typing import Any

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types

from caseflow_agent.intake import intake_agent
from caseflow_agent.registry_toolset import RegistryToolset
from caseflow_agent.zoning import zoning_agent


class SafeAgentTool(AgentTool):
    """AgentTool whose failures return to the model instead of raising.

    With no on_tool_error callbacks, a raised tool exception aborts the whole
    (billed) invocation. Mirror the framework's own single-turn wrapper
    pattern: catch, and hand the model a structured error it can react to.
    """

    async def run_async(self, *, args: dict[str, Any], tool_context: Any) -> Any:
        try:
            return await super().run_async(args=args, tool_context=tool_context)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}


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
)
