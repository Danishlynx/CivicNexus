# ASSUMPTIONS

Working assumptions not (yet) verified, so reviewers know what is load-bearing.
Remove entries as they are confirmed or refuted (refutations become ADRs/BLOCKERS).

- **A-1 — Terraform state is local for Phase 0.** No GCS bucket exists before the
  first apply. A GCS backend + `terraform init -migrate-state` is planned right
  after bootstrap creates the staging bucket. Low risk while a single machine runs
  Terraform.
- **A-2 — `gemini-3.5-flash` verified as a valid current model string**
  (ADR-001 item 6), but Vertex-side pricing is approximate (~$1.50/$9.00 per 1M;
  only the Developer-API table was fetchable). `gemini-3.5-flash-lite`
  (~$0.30/$2.50) is the cost-guard candidate for high-volume paths — human
  decision at the Phase 1 gate. `MODEL_ID` env var is the single override point.
- **A-3 — RESOLVED 2026-08-18: query surface verified live.** `stream_query`
  on the object returned by `client.agent_engines.get(...)` works against the
  deployed instance (four passing smoke runs). Deploy-path consolidation onto
  the ADK CLI is Phase 1 work (ADR-001 item 9).
- **A-4 — Namespace-package layout** (`civicnexus.contracts`, `civicnexus.otel`
  under `libs/*/src/`) is the monorepo convention. Reversible while the codebase is
  small; becomes an ADR if anything forces a change.
- **A-5 — Windows + Git Bash/cmd is the only dev machine.** Makefile recipes are
  single-line and cmd/sh-portable; CI (Cloud Build, Linux) is the arbiter of "works".
- **A-6 — Personal billing, not hackathon credits** (see BLOCKERS B-001). Budget
  alert amounts unchanged at $50/$100/$140 equivalents (INR-denominated) of a
  ~$150 ceiling.
- **A-7 — No automated billing kill switch, by explicit decision (2026-08-18).**
  GCP budgets alert but never stop spending; the budget→Pub/Sub→detach-billing
  pattern was offered and declined — email alerts plus the CLAUDE.md cost guard
  (stop and flag at >$10/day projected) are the agreed protection. Revisit only
  if an alert actually fires.
