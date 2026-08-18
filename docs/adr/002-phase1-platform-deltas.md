# ADR-002: Phase 1 platform deltas — RAG surface, citation keys, agent composition

- **Status:** accepted
- **Date:** 2026-08-18
- **Deciders:** Claude (build agent), per prime directive 10; flagged at the Phase 1 gate

## Context

Phase 1 build-time verification (live docs + installed-SDK source + empirical
probes on project `civicnexus-hack26`; source URLs in the research transcript)
found deltas against ARCHITECTURE.md's assumptions about the RAG and agent
stack.

## Deltas and decisions

1. **RAG API surface:** `vertexai.rag` is deprecated by its own import-time
   warning; the current surface is `agentplatform.Client(...).rag.*` (itself
   marked experimental). We use the Client surface everywhere
   (`scripts/seed_corpus.py` is canonical).
2. **RAG Engine in us-central1 requires serverless mode.** Spanner-backed mode
   is allowlist-restricted (verified empirically: corpus creation 400s with an
   allowlist message). Serverless mode works — verified by creating corpus
   `ragCorpora/7952556497471275008` — but needs (a) a one-time v1beta1 REST
   `ragEngineConfig` patch (no SDK/Terraform surface exists; codified
   idempotently in the seed script) and (b) the `vectorsearch.googleapis.com`
   API (added to Terraform). Region pinning is preserved — no fallback region
   needed.
3. **Retrieval returns no chunk IDs** (verified in SDK types: `RagChunk` has
   only `text` + `page_span`). §3.2's "stable chunk_ids" therefore maps to
   **file identity**: the corpus is ingested one file per code section, named
   `17.44.NNN`, and `source_display_name` is the citation key carried in
   `Citation.chunk_id`. The verifier string-matches quotes against the section
   file's committed text (`data/corpus/`), which is stronger than trusting an
   opaque chunker.
4. **Agent composition:** coordinator delegates via `sub_agents` with
   `mode="single_turn"` (current, GA, in-process — one trace covers the whole
   case). ADK's A2A surface (`RemoteA2aAgent`, `AgentRegistry`) is explicitly
   experimental and Agent Engine's A2A endpoint is v1beta1, HTTP+JSON-only,
   no streaming — so cross-process A2A is reserved for the Phase 3 hot-add
   demo, where dynamic discovery is the point (§6.2's registry flow).
   Structured determinations use `output_schema` (supported together with
   tools per the installed 2.7.1 source, contradicting older docs).
5. **Integration tests use Docker emulators**
   (`gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` for Firestore +
   Pub/Sub): the dev machine has JRE 8 only (emulators need Java 21+), and the
   Pub/Sub emulator's IPv6-default binding is a known Windows trap — pin
   explicit host:port.
6. **Corpus provenance:** Monrovia, CA Municipal Code Ch. 17.44 via American
   Legal Publishing (see `data/CORPUS_SOURCE.md`). One-time manual retrieval,
   text committed, no live scraper shipped; site terms carry no explicit bulk
   policy — **flagged for the human at the Phase 1 gate.**

## Consequences

- Citation verification (Phase 5 verifier) reads `data/corpus/*.txt` directly —
  the committed text is the ground truth the quotes must match.
- The hot-add demo gets a de-risked dry run in Phase 3 since `AgentRegistry` +
  `get_remote_a2a_agent` is exactly its shape.
- A clean-project spin-up (Phase 7 requirement) needs no console steps for RAG:
  Terraform enables APIs, the seed script flips serverless mode and rebuilds
  the corpus from committed text.
