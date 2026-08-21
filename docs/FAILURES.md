# FAILURES.md — every failure, root cause, fix, and what it bought us

Running log (human-directed 2026-08-21). Doubles as source material for the
submission's required "findings and learnings" and the README failure-modes
section. Newest first. "Class eliminated" = the guarantee that now prevents
recurrence, not just the instance fixed.

| # | Failure | Root cause | What we did | Class eliminated / evidence |
|---|---|---|---|---|
| F12 | eval-smoke gate RED after ADR-004 re-wiring (4 regressions, all request_info) | Coordinator LLM *echoes* specialist JSON as final reply; groundedness verifier demands byte-exact verbatim quotes; echo drift fails first pass → critique-retry degrades to request_info | Mechanism isolated from per-case records (verifier_first_pass=False on exactly the 4 regressions); deterministic-composition fix designed (tools stash results in state, code composes reply); ADK-source verification run before ratification ask | Pending fix. Verifier proved it catches quote corruption a human would miss — the fortified-track story, with receipts (results.json, B-009) |
| F11 | Same smoke run: 4 cases unscoreable | Local DNS flaps mid-run (oauth2.googleapis.com unresolvable; known machine issue B-003) + one 81-min hang ending in server disconnect | Recorded; DNS verified healthy after; rerun folded into next chain | None to eliminate (environmental); lesson: never read a red gate as one cause — decompose per-case before reacting |
| F10 | Would-be failure (caught pre-spend): every specialist call would raise on the live engine | Specialists carried mode='single_turn'; AgentTool's private Runner hard-rejects single_turn ROOT agents | 3-agent adversarial verification caught it offline (zero cost) before deploy; mode removed; test pins `mode is None` | Test-enshrined; also killed: legacy deploy script that would resurrect F8 (deleted), instruction gap that would strip verifier_critique from retries |
| F9 | Demo run 2 crash #2: ValidationError streamed mid-run (B-009) | Agent Engine workflow runtime validates a nested single_turn sub-agent node's final text against that agent's output_schema; which agent "speaks last" is LLM-path-dependent; composed multi-capability reply crossed zoning's strict schema | Root-caused from engine traceback + installed ADK source line-by-line; ratified ADR-004: specialists become explicit AgentTools (private Runner, no node validation boundary); coordinator (schema-less) always composes | Schema boundary on the composition path structurally removed; 21 structure tests pin the wiring; ADR-004 records the exception to ADK's own guidance |
| F8 | Demo run 2 crash #1: engine Firestore read failed | Runtime sets GOOGLE_CLOUD_PROJECT to the project NUMBER; Firestore's default-database lookup rejects number form | PROJECT_ID (the id) baked into every engine .env by deploy_agent.py; toolset + consult path prefer it | One env convention everywhere; caught by the fail-closed guard + the exception logging added after F7 — the guard chain worked |
| F7 | Demo run 1: hot-add AFTER step found no specialist | google-cloud-firestore missing from caseflow's deployed requirements; ImportError swallowed by fail-closed guard (silently) | Pinned the dep; fail-closed path now logs its cause to Cloud Logging; pre-flight audits instituted for every billable run | Silent fail-closed eliminated (must log); "audit before spend" became standing practice — F10 is its first save. Honest note: this one was our own slip, not platform mystery |
| F6 | terraform.tfstate truncated to 0 bytes (B-008) | East-teardown apply exited 255 — real state-write failure, misjudged as display noise | Caught at plan (66-to-add tell); backup validated + restored by human one-liner; reconciliation plan verified (1 to add only) | Rule: non-zero exit at end of apply = state-integrity event, check the file immediately; backup duplicated before any recovery |
| F5 | Registry Cloud Run URLs 404 at Google's edge (B-007) | Google-side routing anomaly, proven project-wide (us-east1 clone 404s identically) | Ruled fallback: REGISTRY_MODE=firestore interim — approved-only filter moved INTO the Firestore query (tool-poisoning defense intact); registry service + IAM stay authoritative; reverts when edge heals | Demo unblocked without weakening governance; ADR-003 addendum records the honest deviation |
| F4 | A2A endpoint dead on CLI deploys (spike, 4 variants) | CLI/SDK validators reject agent_card config; platform card/message routes 400/404 even after raw REST PATCH | Evidence-precision spike table; ruled: proven :streamQuery transport, A2A deferred to Phase 6 | Dependent code never built on an unproven transport; spike-before-build practice validated |
| F3 | Pro/newer-Flash models HTTP 417 (Phase 2) | Fresh personal project served a restricted roster (exactly 3.5-flash + flash-lite) | Documented as B-006 accuracy-ceiling factor; re-probed 2026-08-21: roster EXPANDED (2.5-pro, 3.1-pro-preview, 3.6/3.7-flash now serve) — Pro ablation queued for Phase 5 | Claims time-boxed: roster facts get re-probed, never assumed stale-true |
| F2 | "No traces from hello agent" false alarm (B-005) | OTel-native spans invisible to legacy Cloud Trace v1 list API used by polling scripts | Human console check disproved it (24 spans present); rule: verify in Trace Explorer, never v1 API; google-adk[otel-gcp] extra made mandatory | Read-path vs write-path distinction in all "X is broken" claims |
| F1 | Decision accuracy 65–80% vs 85% gate (B-006, open) | Over-asking (request_info where code already decides) + one wrong-section approval; prompt-tuning measured as whack-a-mole (n=20 variance) | Threshold NEVER lowered; gate stays visibly red; verifier added (stabilized 80%, groundedness 100%); remaining levers queued: Pro-at-decision ablation, per-agent retrieval | Prime directive 9 held under pressure; every eval report shows the honest number |

## Standing lessons (the short version)

1. **Audit before spend.** Every billable run gets a pre-flight; two fatal
   configs were caught at zero cost this way.
2. **Guards must be loud.** Fail-closed without logging turned a 1-line bug
   (F7) into a billed demo failure; every guard now names its cause.
3. **Decompose red gates per-case** before reacting (F11/F12 were two
   different problems wearing one number).
4. **Platform unknowns are found, not planned away** — on a months-old
   stack, the plan's job is making each unknown cheap: gates, spikes,
   fail-closed, small billable steps.
5. **The verifier is the product.** F12 is the fortified-track pitch:
   the system caught its own corrupted citations and refused to ship them.
