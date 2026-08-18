"""Phase 0 hello agent — exists solely to prove deploy + one Cloud Trace span.

Import path and constructor verified against live ADK docs before first deploy
(ASSUMPTIONS.md A-3); `MODEL_ID` is the single override point for the model
string (ARCHITECTURE.md §10 flags).
"""

import os

from google.adk.agents import Agent

# The Agent Engine runtime pre-sets GOOGLE_CLOUD_LOCATION to the deploy region,
# but Gemini 3.x serves only from the global endpoint on this project (ADR-001
# item 8) — so model routing must force-override it. MODEL_LOCATION is the
# escape hatch if regional serving ever returns.
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("MODEL_LOCATION", "global")

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
