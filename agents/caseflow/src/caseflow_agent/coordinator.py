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
from caseflow_agent.zoning_extract import zoning_extract_agent


def select_zoning_specialist(mode: str) -> Agent:
    """The zoning specialist for a decision mode (ADR-008, proposed).

    ``code`` swaps in an agent that extracts facts and reaches no conclusion;
    the driver then applies the written rules in ``civicnexus.decision``.
    Anything else — including the default — keeps today's deciding agent.

    Both agents are named "zoning" and fill the same routing slot, so the
    coordinator's instruction is identical either way and the default path is
    byte-identical to what it was before the flag existed.
    """
    return zoning_extract_agent if mode == "code" else zoning_agent


DECISION_MODE = os.environ.get("DECISION_MODE", "model")
_zoning_specialist = select_zoning_specialist(DECISION_MODE)

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
    sub_agents=[intake_agent, _zoning_specialist],
    tools=[RegistryToolset()],
)
