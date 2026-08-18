# PROGRESS

**Current phase: 0 — COMPLETE (gate passed 2026-08-18); Phase 1 awaiting human go.**
Last updated: 2026-08-18. Companion files: [BLOCKERS.md](BLOCKERS.md), [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Phase status

| Phase | Status |
|---|---|
| 0 Skeleton | **COMPLETE** — `make verify-phase-0` PASS (test + smoke + trace URL); human reviewed traces at the gate |
| 1–7 | not started |

## Phase 0 checklist

Exit criteria: `make smoke` green + a concrete Cloud Trace URL recorded below.

- [x] Git repo on `main`; `Docs/` → `docs/` casing fixed (no commits yet — the
      initial commit series awaits human approval per working agreement)
- [x] uv workspace (Python 3.12): root + `libs/contracts` + `libs/otel` + `agents/hello`
- [x] `libs/contracts`: event envelope + 12 spec topics + 13 case states; unknown
      fields rejected (`extra="forbid"`), timestamps must be tz-aware; 11 contract tests
- [x] `libs/otel`: structured JSON logging (Cloud Logging field shape; extras
      cannot clobber canonical fields); 7 unit tests
- [x] Makefile: full CLAUDE.md target contract; every unimplemented target
      (including `verify-phase-1..7`) fails honestly naming its phase; bare
      `make` is a safe `help` target, never `terraform apply`
- [x] Pre-commit **config authored and hook installed** (`.git/hooks/pre-commit`):
      ruff + format + uv-lock check + gitleaks (local 8.30.1) + mypy + terraform fmt
- [x] CI skeleton `cloudbuild.yaml` (pinned images) — file only; trigger wiring
      needs the GCP project
- [x] Terraform baseline: 20 APIs, budget alerts $50/$100/$140 on **gross** spend
      (credits excluded so promo credits can't mute alerts), staging bucket
- [x] Live-docs verification of the Google agent stack → [ADR-001](docs/adr/001-live-docs-deltas-at-build-start.md)
- [x] Hello ADK agent (google-adk 2.7.1) + deploy/smoke/verify scripts (deploy
      guarded against duplicate instances; smoke asserts real model text)
- [x] Multi-agent spec-compliance review of the scaffold: 31 findings raised,
      30 confirmed after adversarial refutation, fixes applied (2 consciously
      deferred — see "Known gaps" below)
- [x] `make bootstrap` PASS — 20 APIs, budget `338dd463` with 3 alert
      thresholds (INR-denominated: account currency is INR, see evidence),
      staging bucket `civicnexus-hack26-agent-staging` (B-002 resolved)
- [x] Hello agent deployed to Agent Engine — live instance
      `projects/382264320396/locations/us-central1/reasoningEngines/7337306624207355904`
      (CLI-built with `--otel_to_cloud`; model calls route via the global
      endpoint per ADR-001 items 8–9)
- [x] `make smoke` PASS — agent replied over the deployed stack (4 passing runs)
- [x] Trace URL recorded — trace `ac70d29773a2694335410ef54538fed4` (root span
      `1c739761e187c1f5`, `invoke_workflow hello_agent`, 17:31:58 IST, live
      instance), clicked through and pasted by the human at the gate:
      https://console.cloud.google.com/traces/explorer;traceId=ac70d29773a2694335410ef54538fed4;spanId=1c739761e187c1f5;duration=PT1H?project=civicnexus-hack26
      B-005 resolved: 24 spans across all three instances in Trace Explorer
      (`invoke_workflow` → `invoke_agent` → `call_llm` → `generate_content
      gemini-3.5-flash`); the v1 list API simply cannot see OTel-native spans.

## Evidence log

- **2026-08-18 (post-review-fixes) — full local chain, output observed directly:**
  - `uv lock --check` → "Resolved 111 packages"
  - `uv run ruff check .` → "All checks passed!"
  - `uv run ruff format --check .` → "23 files already formatted"
  - `uv run mypy libs agents scripts` (strict) → "Success: no issues found in 14 source files"
  - `uv run pytest` → "17 passed", coverage 100% on `libs/` (gate ≥80%)
  - `terraform fmt -check -recursive` → clean; `terraform validate` → "Success! The configuration is valid."
  - `pre-commit install` → "pre-commit installed at .git\hooks\pre-commit"
- **2026-08-18 — build-time research:** live-docs verification with source URLs
  recorded in ADR-001 (model string `gemini-3.5-flash` confirmed; SDK deploy
  surface confirmed; `--otel_to_cloud` supersedes deprecated `--trace_to_cloud`).
- **2026-08-18 — GCP bring-up (all outputs observed directly):**
  - Project `civicnexus-hack26` created by the human; billing linked to
    `0181F3-EBFDD3-297923` (INR-denominated — budget uses INR equivalents:
    ₹13,000 ceiling, alerts ₹4,333/₹8,667/₹12,133 ≈ $50/$100/$140, gross spend).
  - Manual bootstrap step (recorded per prime directive 6): `gcloud services
    enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com` —
    required before the first terraform apply on any fresh project; both APIs
    are also in the Terraform list so state stays authoritative.
  - `make bootstrap` → PASS (three runs to green: Service Usage chicken-and-egg,
    propagation retry, then budget currency fix).
  - `make deploy` → PASS; `make smoke` → PASS ×4, e.g. reply: "Yes, the
    CivicNexus hello agent is alive and online."
  - Tracing: resolved at the gate — spans existed all along; the legacy v1 list
    API can't see OTel-native spans (B-005, ADR-001 item 10). Human verified 24
    spans in Trace Explorer and clicked through trace
    `ac70d29773a2694335410ef54538fed4`.
  - **`make verify-phase-0` → PASS** (test chain green, live smoke reply
    "Yes, I am alive and online to confirm that the connection works.", trace
    URL assertion satisfied). **Phase 0 exit criteria met.**

## Known gaps (deliberate, tracked)

- **Nothing has been deployed to GCP**; `make bootstrap`/`deploy`/`smoke` have
  never run against a real project. The SDK *query* surface in `scripts/smoke.py`
  is best-effort until first deploy (deploy surface is verified; query is not).
- Trace verification is currently "smoke asserts a model reply + human records a
  concrete trace-id URL that `verify-phase-0` validates"; a Cloud Trace API
  assertion can replace the human step later if wanted.
- `EventEnvelope.payload` is a plain dict (mutable inside a frozen model, and
  makes the model unhashable in practice) — typed per-event payload models are
  Phase 1 work when the state machine lands.
