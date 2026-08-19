"""Coordinator: routes casework tasks to specialist sub-agents (§3.1).

Phase 1 slice: two specialists, in-process composition (ADR-002 item 4). The
registry-driven capability discovery and per-agent identities arrive in
Phase 3; the routing contract here (task field selects the specialist) stays.
"""

import os

from google.adk.agents import Agent
from google.genai import types as genai_types

from caseflow_agent.intake import intake_agent
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
        '- task "review": delegate the contained structured application to the '
        "zoning agent.\n"
        "Return the specialist's JSON output verbatim as your entire reply - no "
        "commentary, no code fences. If the task field is missing or unknown, "
        'reply with {"error": "unknown task"}.'
    ),
    sub_agents=[intake_agent, zoning_agent],
)
