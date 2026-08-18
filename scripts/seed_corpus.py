"""Seed the municipal-code corpus into RAG Engine (idempotent).

Passing means: the project's RAG engine runs in serverless mode (the only
non-allowlisted mode in us-central1 — ADR-002), the corpus exists, every
section file under ``data/corpus/`` is uploaded exactly once with its section
number as display name, and a retrieval self-check returns the home-occupation
section for the canonical demo query.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any

CORPUS_DISPLAY_NAME = "civicnexus-municipal-code"
CORPUS_DIR = Path("data/corpus")
SELF_CHECK_QUERY = "May a home occupation operate in an accessory structure such as a garage?"
SELF_CHECK_EXPECT = "17.44.100"


def ensure_serverless_mode(project: str, region: str) -> None:
    """Switch the project's RAG engine config to serverless mode if needed.

    No SDK surface exists for this yet (observed 2026-08-18); uses the v1beta1
    REST API directly. Spanner mode is allowlist-restricted in us-central1.
    """
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    name = f"projects/{project}/locations/{region}/ragEngineConfig"

    current = session.get(f"{base}/{name}").json()
    if "serverless" in current.get("ragManagedDbConfig", {}):
        print("seed_corpus: RAG engine already in serverless mode")
        return
    resp = session.patch(
        f"{base}/{name}",
        json={"name": name, "ragManagedDbConfig": {"serverless": {}}},
    )
    resp.raise_for_status()
    print("seed_corpus: switched RAG engine config to serverless mode")
    time.sleep(20)


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("seed_corpus: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    section_files = sorted(CORPUS_DIR.glob("*.txt"))
    if not section_files:
        print(f"seed_corpus: no section files in {CORPUS_DIR}", file=sys.stderr)
        return 1

    import agentplatform
    from agentplatform import types
    from google.genai import types as genai_types

    ensure_serverless_mode(project, region)
    client = agentplatform.Client(project=project, location=region)

    listing = client.rag.list_corpora()
    corpus = next(
        (c for c in (listing.rag_corpora or []) if c.display_name == CORPUS_DISPLAY_NAME),
        None,
    )
    if corpus is None:
        corpus = client.rag.create_corpus(
            rag_corpus=types.RagCorpus(display_name=CORPUS_DISPLAY_NAME)
        )
        print(f"seed_corpus: created corpus {corpus.name}")
    else:
        print(f"seed_corpus: reusing corpus {corpus.name}")
    corpus_name: str = corpus.name or ""

    files_listing = client.rag.list_files(name=corpus_name)
    existing = {f.display_name for f in (files_listing.rag_files or [])}
    uploaded = 0
    for path in section_files:
        if path.stem in existing:
            continue
        client.rag.upload_file(
            corpus_name=corpus_name,
            path=str(path),
            display_name=path.stem,
            upload_rag_file_config=types.UploadRagFileConfig(
                rag_file_chunking_config=types.RagFileChunkingConfig(
                    chunk_size=512, chunk_overlap=100
                )
            ),
        )
        uploaded += 1
        print(f"seed_corpus: uploaded {path.stem}")
    print(f"seed_corpus: {uploaded} uploaded, {len(existing)} already present")

    response: Any = client.rag.retrieve_contexts(
        vertex_rag_store=genai_types.VertexRagStore(
            rag_resources=[genai_types.VertexRagStoreRagResource(rag_corpus=corpus_name)],
        ),
        query=types.RagQuery(
            text=SELF_CHECK_QUERY,
            rag_retrieval_config=genai_types.RagRetrievalConfig(top_k=5),
        ),
    )
    contexts = list(response.contexts.contexts)
    hits = [(c.source_display_name, round(c.score, 3)) for c in contexts]
    print(f"seed_corpus: self-check retrieval: {hits}")
    if not any(name == SELF_CHECK_EXPECT for name, _ in hits):
        print(
            f"seed_corpus: FAIL - {SELF_CHECK_EXPECT} not in top-5 for the demo query",
            file=sys.stderr,
        )
        return 1
    print(f"seed_corpus: self-check passed ({SELF_CHECK_EXPECT} retrieved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
