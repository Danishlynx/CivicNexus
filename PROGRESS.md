# PROGRESS

**Current phase: 1 — COMPLETE (verify-phase-1 PASS 2026-08-18); awaiting human gate review, then Phase 2.**
Last updated: 2026-08-18. Companion files: [BLOCKERS.md](BLOCKERS.md), [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Phase status

| Phase | Status |
|---|---|
| 0 Skeleton | **COMPLETE** — `make verify-phase-0` PASS (test + smoke + trace URL); human reviewed traces at the gate |
| 1 Vertical slice | **COMPLETE** — `make verify-phase-1` PASS; cited determination reached PENDING_HUMAN on the live stack (details below) |
| 2 Evals first | **COMPLETE (gate passed 2026-08-20)** — human decision at gate: lock the honest 80% baseline, advance with B-006 open. Harness + 20 verified cases + 7 recorded runs; verifier built early; CI live (2nd-gen trigger, smoke on every push) |
| 3 Fleet + governance | IN PROGRESS — ADR-003 ratified w/ conditions; registry contracts + service drafted; A2A spike run (see ADR-003 evidence record); CI green end-to-end |
| 4–7 | not started |

## IAM evidence log (per Working Agreement: role + principal + reason, always)

| Date | Role | Principal | Reason |
|---|---|---|---|
| 2026-08-18 | roles/aiplatform.user | service-382264320396@gcp-sa-aiplatform-re.iam.gserviceaccount.com (Reasoning Engine service agent) | deployed agents must query the RAG corpus (fixed the 403 on ragCorpora.get) |
| 2026-08-19 | roles/aiplatform.user | 382264320396@cloudbuild.gserviceaccount.com | CI eval-smoke step queries the deployed engine |
| 2026-08-19 | roles/aiplatform.user | 382264320396-compute@developer.gserviceaccount.com | same, for whichever identity Cloud Build runs as |
| 2026-08-20 | roles/cloudbuild.builds.builder | 382264320396-compute@developer.gserviceaccount.com | named build SA needs Cloud Build's working set; INTERNAL_ERROR before any step otherwise |
| 2026-08-20 | roles/logging.logWriter | 382264320396-compute@developer.gserviceaccount.com | build logs with CLOUD_LOGGING_ONLY under a named SA |
| 2026-08-20 | roles/aiplatform.user | sa-caseflow@, sa-safety@, sa-letters@, sa-treepres@civicnexus-hack26.iam.gserviceaccount.com (4 grants, human-authorized in advance) | per-agent identities (§6.1/ADR-003): each agent calls models + queries the RAG corpus |
| 2026-08-20 | Data Access audit logs (DATA_READ, DATA_WRITE) on aiplatform.googleapis.com | project-wide audit config, human-authorized in advance | the deliberate-deny test must produce an auditable 403 entry |
| 2026-08-20 | roles/iam.serviceAccountUser (scoped to the 4 sa-* accounts only) | user:danishlynx@gmail.com | deployer must hold actAs to bind agent SAs to runtimes; asked and approved before applying |

Standing note: all grants above are Terraform-managed (iam.tf, ci.tf). Future
IAM changes are ask-first per the Working Agreement in CLAUDE.md.

## Phase 2 evidence (2026-08-19, all output observed directly)

- **PermitBench**: 20 golden cases across 15 corpus sections; 15 drafted by a
  5-drafter/5-verifier adversarial pipeline (every expectation attacked
  against the statute text before acceptance), 5 hand-authored on §17.44.100;
  12-case smoke subset; canaries in every doc; loader enforces that expected
  citations exist in the corpus. Runner (backoff per §7.5, per-case error
  isolation), metrics with §9.4 gates, auto-generated `docs/eval-report.md`.
- **Five full live runs** (~$5 total): 80% → 70% → 80% → 65% → 70% decision
  accuracy; groundedness 90–100%; citation P/R 0.88–0.95; leak rate 0 every
  run. Config locked after run 5 (temp 0, ordered decision rule with
  hedged-facts clause, caseflow v0.2.0). Full analysis and the two headline
  failure classes (over-asking; one verbatim-quote-from-wrong-section
  approval) in B-006 — the Phase 5 verifier is the designed remedy for both.
- **Eval harness caught a real regression before it shipped** (run 4's 65%
  from a plausible-looking prompt clause) — the subsystem is doing its job.
- **CI**: build config with Firestore-emulator sidecar + eval-smoke step
  committed; trigger blocked: Google no longer accepts new triggers on
  1st-gen GitHub connections (bare 400s; confirmed via docs), so the human
  redoes the connect on the 2nd-gen path in us-central1, then the trigger is
  Terraform-applied.

## Phase 1 evidence (2026-08-18, all output observed directly)

Exit criterion (§11): one case reaches PENDING_HUMAN with a cited
determination; e2e passes. **Met, twice, on the real deployed stack:**

- Deployed fleet: `civicnexus-caseflow` (coordinator + intake + zoning,
  in-process composition per ADR-002 item 4) — Agent Engine instance
  `projects/382264320396/locations/us-central1/reasoningEngines/2118760555991793664`,
  CLI-deployed with `--otel_to_cloud` and the `google-adk[otel-gcp]` extra.
- Live case `case-a61c62612c0c`: intake parsed the synthetic Maria fixture
  (complete=true) → RECEIVED → TRIAGED → IN_REVIEW → zoning determination
  **deny @ confidence 1.0 citing §17.44.100** with the verbatim quote "No
  employees are allowed other than members of the resident family;" (correct:
  the fixture's helper is a non-resident sister) → PENDING_HUMAN. Every
  transition published its §5 event and audit row (message ids in the log).
- Formal `make verify-phase-1` → PASS: full test chain (102 tests incl.
  emulator integration, 97%+ coverage, strict mypy on 38 files) + a second
  live case `case-21c09bb0094b` → **request_info @ 1.0, same §17.44.100
  citation, verbatim-verified** → PENDING_HUMAN.
- Grounding is machine-checked by the driver: citation section files must
  exist in `data/corpus/` and quotes must match the committed text verbatim
  (whitespace-normalized). Canary string did not surface in agent output.

**Deltas/flags for the gate:**
1. Outcome variance across runs (deny vs request_info on identical facts) —
   both defensible readings of §17.44.100(A); characterizing this is exactly
   Phase 2's eval work.
2. IAM: deployed agents currently run as the shared Reasoning Engine service
   agent with a coarse `roles/aiplatform.user` grant (Terraform `iam.tf`) —
   required for RAG retrieval (403 observed without it); replaced by
   per-agent least-privilege SAs in Phase 3 (§6.1).
3. Corpus rights: public-record municipal code via American Legal Publishing,
   one-time manual retrieval with attribution (`data/CORPUS_SOURCE.md`,
   ADR-002 item 6) — human sign-off requested at this gate.
4. Cost hygiene (post-gate, 2026-08-18): the Phase 0 hello instance was
   decommissioned — caseflow supersedes it and idle Agent Engine instances are
   the main idle-cost candidate. Evidence is unaffected (git history, traces,
   this file); redeployable any time via `scripts/deploy_hello.py`. Exactly
   one instance remains deployed: `civicnexus-caseflow`.

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
