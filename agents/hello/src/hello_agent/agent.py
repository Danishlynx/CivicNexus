"""Phase 0 hello agent — exists solely to prove deploy + one Cloud Trace span.

Import path and constructor verified against live ADK docs before first deploy
(ASSUMPTIONS.md A-3); `MODEL_ID` is the single override point for the model
string (ARCHITECTURE.md §10 flags).
"""

import os

from google.adk.agents import Agent

root_agent = Agent(
    name="hello_agent",
    model=os.environ.get("MODEL_ID", "gemini-3.5-flash"),
    description="CivicNexus walking-skeleton agent; replies briefly to prove the path works.",
    instruction=(
        "You are the CivicNexus hello agent, a deployment smoke check. "
        "Reply to any message in one short sentence confirming you are alive. "
        "Do not claim any casework capability."
    ),
)
