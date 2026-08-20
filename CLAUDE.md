# CLAUDE.md — CivicNexus build handoff

You are Claude Code, building **CivicNexus**: a governed multi-agent platform for municipal
permit casework, entered in Google's All Things Agentic Hackathon (Fortified Enterprise
Fleet track). Deadline: Aug 31, 2026, 5:00 PM PT. Internal freeze Aug 29, submit Aug 30.

**Read first, in order:** `docs/PRODUCT.md` (what and why), `docs/ARCHITECTURE.md`
(authoritative spec — every section number referenced below points there). This file governs
*how you work*. If this file and ARCHITECTURE.md ever conflict, ARCHITECTURE.md wins and you
flag the conflict in `BLOCKERS.md`.

---

## Prime directives (non-negotiable)

1. **Truthfulness above all.** Never fabricate command output, eval numbers, screenshots,
   trace links, or "it works" claims. If something is broken, unverified, or assumed, say so
   explicitly in `PROGRESS.md`. A judged project with honest gaps beats one with invented
   results — and invented results are disqualifying in every sense.
2. **Phase discipline.** Work only within the current phase (§11). Finish its exit criteria,
   update `PROGRESS.md` with evidence, commit, then STOP for human review at the gate.
   Do not start the next phase unprompted.
3. **Secrets.** Never print, log, or commit secrets. No service-account key files, ever —
   runtime identity only. `gitleaks` runs in pre-commit and CI; it must pass.
4. **Safety rails stay up.** `SAFE_MODE=true` is the default everywhere; side-effect tools
   no-op without a human-minted approval token. Never disable a guardrail, skip the
   verifier, or bypass the gateway "temporarily" to make a test pass.
5. **Tests define done.** Every exit criterion is an executable check. Green before moving
   on. No `TODO` on main without a tracked issue reference.
6. **Terraform-only infrastructure.** No console click-ops after initial project creation.
   If you must change something manually to unblock, record it in `BLOCKERS.md` and
   backfill Terraform in the same phase.
7. **Small conventional commits, PRs even solo.** One logical change per commit
   (`feat:`, `fix:`, `test:`, `infra:`, `docs:`).
8. **Cost guard.** Gemini Flash by default, Cloud Run `min-instances=0`, eval smoke on PRs
   and full runs nightly only. If projected spend exceeds ~$10/day or a budget alert fires,
   stop and flag before continuing.
9. **Never lower an eval threshold to pass a gate.** Fix the system, or write the failure
   honestly into `docs/eval-report.md` and `BLOCKERS.md`.
10. **Verify fast-moving product details against live docs at build time** — the exact
    Vertex model string for Gemini 3.5 Flash, current ADK APIs, Agent Engine deploy syntax,
    Memory Bank service names, Model Armor endpoints. Google's agent stack moves monthly;
    your training memory is stale by definition. When docs contradict ARCHITECTURE.md,
    follow the docs and record the delta as an ADR.

## Working Agreement (amendment, ratified by the human 2026-08-20)

**ASK FIRST:** any IAM/permission change (role + principal + reason named in the
ask); anything creating billed infrastructure or projecting past ~$10/day;
anything touching data deletion or retention; any change to guardrails, eval
thresholds, or SAFE_MODE; any deviation from a ratified ADR or ruling.

**PROCEED AND REPORT:** retries, lint/format/tests, reading logs and docs, code
that implements an already-ratified decision, spike variations under the
evidence-precision rule.

**AMBIGUOUS:** one-line flag before acting. The flag costs a minute; the
reverse costs trust.

**Evidence-precision rule:** spike/experiment writeups state exactly which
variant ran and which claim it proves. "Works under lean config X" is not
"works." Claims never drift wider than the test that produced them.

**IAM evidence standard:** every grant names the role, the principal, and the
reason in the evidence log — never summarized as "standard roles."

## Session loop (every working session)

1. Read `PROGRESS.md` (current phase, last evidence) and `BLOCKERS.md`.
2. Plan: list the files you'll touch and the exit criterion you're driving toward.
3. Implement in small steps; run unit tests as you go.
4. Run the phase verifier: `make verify-phase-N`.
5. Update `PROGRESS.md` with evidence links (test output, trace URL, deployed revision).
6. Commit. At a phase boundary: stop and request human review.

## When blocked (15-minute rule)

If blocked longer than ~15 minutes of real effort: write a `BLOCKERS.md` entry with the
symptom, two candidate paths, and your recommendation; take the safest *reversible* path;
tag the human. **Expected blocker:** managed Agent Gateway / Agent Registry preview access
may be denied — that is not a failure, it is why `GATEWAY_MODE=selfhosted` exists (§6.2).
Build selfhosted first regardless; attempt managed bind in Phase 6 only.

## Bootstrap (Phase 0 prerequisites)

Human provides: `PROJECT_ID`, `REGION` (us-central1), billing enabled, the $150 hackathon
credits applied (form deadline Aug 28, 12:00 PM PT), and `gcloud auth application-default
login` completed. Then:

- Enable APIs (Terraform does this, but verify): Vertex AI, Cloud Run, Pub/Sub, Firestore,
  Cloud Tasks, Cloud Scheduler, BigQuery, Cloud Build, Secret Manager, Cloud Trace,
  Model Armor.
- `make bootstrap` = terraform init/apply baseline + budget alerts at $50/$100/$140.
- Deploy the hello ADK agent to Agent Engine; confirm one trace in Cloud Trace.
- Record the trace URL in `PROGRESS.md`. That completes Phase 0.

## Make targets contract (implement these; each prints PASS/FAIL)

| Target | Passing means |
|---|---|
| `make bootstrap` | Infra applied clean; budget alerts exist |
| `make deploy` | All services/agents deployed from source via Cloud Build |
| `make smoke` | Hello-path e2e against staging returns 200 + emits a trace |
| `make test` | Lint, types, unit, contract tests all green |
| `make eval-smoke` | 12-case subset meets gates (§9.4) |
| `make eval-full` | ~80 cases run; `results.json` + `docs/eval-report.md` regenerated |
| `make demo-hotadd` | New agent registered+approved mid-run; coordinator routes to it, no redeploy |
| `make demo-injection` | Poisoned PDF blocked by Model Armor; quarantine + incident + trace asserted |
| `make demo-timewarp` | 12-day gap (CLOCK_MULTIPLIER) → resume with Memory Bank recall asserted |
| `make dlq-replay` | Dead-lettered event replays without duplicate side effects |
| `make verify-phase-N` | All exit criteria for phase N |
| `make teardown` | Full infra destroy (do NOT run before judging ends Oct 1) |

## Phase gates (condensed — full detail in ARCHITECTURE §11)

| Phase | Exit proof | Human action at gate |
|---|---|---|
| 0 Skeleton | smoke green; trace URL | Confirm project/billing/credits |
| 1 Vertical slice | Cited determination reaches PENDING_HUMAN; e2e test | Review one case end to end |
| 2 Evals first | eval-smoke green in CI; baseline recorded | Sanity-check golden cases |
| 3 Fleet + governance | demo-hotadd passes; deliberate-deny audit entry | Review IAM matrix + registry flow |
| 4 Durability | demo-timewarp passes | Watch the resume live once |
| 5 Armor + drills | demo-injection passes; block 15/15; ablations captured | Review incident view |
| 6 Console + freeze | Full case operable from UI alone | UX pass; freeze declared |
| 7 Ship | Clean-project spin-up verified; video recorded; submitted | Record video; submit |

## Data and fixture rules

Synthetic data only: faker with fixed seeds; no real names, addresses, emails, or parcel
numbers. Plant canary strings (`CANARY-<id>`) in synthetic PII fields — appearing anywhere
downstream is a leak and a test failure. The simulated inbox never sends real email. The
municipal code corpus uses one chapter of a real public code with attribution in
`data/CORPUS_SOURCE.md`.

## Coding standards (quick list)

Python 3.12 + `uv`; `ruff` + `mypy` (strict in `libs/`); Pydantic models in
`libs/contracts` are the single source of truth for every schema; docstrings on public
functions; structured JSON logging via `libs/otel` only (never bare `print` in services);
per-tool timeouts from the table in `libs/tools`; ADR (`docs/adr/`) for every irreversible
choice.

## Anti-goals

No features beyond the spec. No framework swaps. No second cloud. No "quick hack" that
bypasses the gateway, the verifier, or SAFE_MODE. No real external side effects, ever.
When in doubt, smaller and verified beats bigger and assumed.

## Definition of done (submission checklist)

- [ ] Hosted console URL live (scale-to-zero) and linked in the Devpost form
- [ ] Repo shared with testing@devpost.com and cloudhackathons@google.com (if private)
- [ ] README: spin-up instructions verified from a **clean** project; architecture diagram;
      eval results table; failure-modes section; AI-assistance + pre-existing-code
      disclosure; corpus attribution; `THIRD_PARTY.md`
- [ ] `make eval-full` results current; ablation charts exported
- [ ] Video ≤4:00, public on YouTube, English: problem (0:30) → diagram (0:20) → one
      continuous unedited run hitting hot-add, injection block, time-warp (≈2:00) → eval
      dashboard (0:30) → GCP console proof (0:40)
- [ ] Blog post published with the required line "created for the purposes of entering this
      hackathon"; social post with #AllThingsAgenticHackathon
- [ ] Submitted on Devpost by Aug 30 (deadline Aug 31, 5:00 PM PT)

## Reference

Claude Code documentation (verify current config/behavior there, not from memory):
https://docs.claude.com/en/docs/claude-code/overview — this file is read automatically from
the repo root at session start.
