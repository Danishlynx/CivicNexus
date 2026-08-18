"""Caseflow app root — the deployable Phase 1 fleet slice.

The Agent Engine runtime pre-sets GOOGLE_CLOUD_LOCATION to the deploy region,
but Gemini 3.x serves only from the global endpoint on this project (ADR-001
item 8) — model routing must force-override. MODEL_LOCATION is the escape
hatch; RAG retrieval stays regional via its own client (rag_tool).
"""

import os

os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("MODEL_LOCATION", "global")

from caseflow_agent.coordinator import coordinator

root_agent = coordinator
