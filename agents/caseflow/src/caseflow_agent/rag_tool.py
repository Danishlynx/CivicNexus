"""Municipal-code retrieval tool for the zoning agent.

Queries the RAG Engine corpus; each hit returns the section number (the stable
citation key, ADR-002 item 3) and the retrieved text the agent must quote
verbatim. RAG calls stay regional (us-central1) even though model inference
routes globally — the client here is constructed with an explicit location.
"""

import os
from typing import Any

_TOP_K = 6


def lookup_municipal_code(query: str, _client: Any | None = None) -> dict[str, Any]:
    """Search the municipal code for provisions relevant to `query`.

    Returns {"sections": [{"section": "17.44.100", "text": "..."}]}. Cite only
    section numbers returned here, and quote spans verbatim from their text.
    """
    corpus_name = os.environ["CORPUS_NAME"]
    if _client is None:
        import agentplatform

        _client = agentplatform.Client(
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "")),
            location=os.environ.get("RAG_LOCATION", "us-central1"),
        )
    from agentplatform import types
    from google.genai import types as genai_types

    response = _client.rag.retrieve_contexts(
        vertex_rag_store=genai_types.VertexRagStore(
            rag_resources=[genai_types.VertexRagStoreRagResource(rag_corpus=corpus_name)],
        ),
        query=types.RagQuery(
            text=query,
            rag_retrieval_config=genai_types.RagRetrievalConfig(top_k=_TOP_K),
        ),
    )
    sections = [
        {"section": c.source_display_name, "text": c.text} for c in response.contexts.contexts
    ]
    return {"sections": sections}
