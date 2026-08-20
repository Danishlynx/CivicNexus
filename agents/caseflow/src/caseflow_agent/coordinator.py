"""Coordinator: routes casework tasks to specialist sub-agents (§3.1).

Phase 1 slice: two specialists, in-process composition (ADR-002 item 4). The
registry-driven capability discovery and per-agent identities arrive in
Phase 3; the routing contract here (task field selects the specialist) stays.
"""

import os

from google.adk.agents import Agent
from google.genai import types as genai_types

from caseflow_agent.intake import intake_agent
from caseflow_agent.registry_toolset import RegistryToolset
from caseflow_agent.zoning import zoning_agent

coordinator = Agent(
    name="coordinator",
    model=os.environ.get("MODEL_ID", "gemini-3.5-flash"),
    generate_content_config=genai_types.GenerateContentConfig(temperature=0.0),
    description="Plans and delegates permit-case work to specialist agents.",
    instruction=(
        'You coordinate permit casework. The user message is JSON with a "task" '
        "field.\n"
        '- task "intake": delegate the contained raw application to the intake '
        "agent.\n"
        '- task "review": the message contains the structured application and a '
        '"capabilities" list naming the reviews this permit type requires. For '
        'the "zoning" capability, delegate to the zoning agent. For any OTHER '
        "capability, use the matching consult_<agent> tool if one is available "
        "- these tools are the registry's currently APPROVED specialists. If a "
        "required capability has no matching specialist, note it in the output "
        'as {"missing_capability": "<name>"} alongside the findings you did '
        "obtain.\n"
        "When a review requires multiple capabilities, collect every "
        'specialist\'s finding and reply with JSON: {"findings": '
        '[{"capability": ..., "finding": <specialist JSON>}]}. For a single '
        "zoning-only review, return the zoning agent's JSON verbatim.\n"
        "Return ONLY JSON - no commentary, no code fences. If the task field "
        'is missing or unknown, reply with {"error": "unknown task"}.'
    ),
    sub_agents=[intake_agent, zoning_agent],
    tools=[RegistryToolset()],
)
