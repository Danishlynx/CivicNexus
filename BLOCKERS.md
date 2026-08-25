# BLOCKERS

Active blockers and risks, newest first. Format per CLAUDE.md: symptom, candidate
paths, recommendation, who acts.

---

## B-009 — demo run 2: two engine-side defects; composition crash is a demo-reliability trap (OPEN, fix decision with human)

**Symptom (2026-08-21, run 2 of demo-hotadd):** BEFORE review crashed
mid-stream. Engine logs (Cloud Logging, both tracebacks captured) show:

1. **Firestore project-number 404 (root-caused, fix coded):**
   `_fetch_via_firestore` used `GOOGLE_CLOUD_PROJECT`, which the Agent
   Engine runtime sets to the project NUMBER; Firestore's default-database
   lookup rejects number form ("The database (default) does not exist for
   project 382264320396"). The fail-closed guard worked and the new
   exception logging captured it — the toolset degraded to zero tools
   honestly. Fix: bake PROJECT_ID (the id) into engine .env; toolset
   prefers it. CODED, awaiting the next approved redeploy.

2. **Sticky-delegation composition trap (decision needed):** ADK
   `sub_agents` transfer makes the last-speaking agent own the final
   reply. On MULTI-capability reviews, if the zoning specialist (strict
   `output_schema=ReviewFindingOut`) is the last responder, its schema
   rejects the coordinator-style composed reply
   (`{"findings": [...], "missing_capability": ...}`) — engine raises
   ValidationError into the stream. Which agent speaks last is
   LLM-path-dependent: run 1 BEFORE composed from the coordinator (fine),
   run 2 BEFORE did not (crash). Single-capability eval replies satisfy
   the schema, which is why 7 PermitBench runs never saw this. As-is, the
   demo (and the submission video) is nondeterministically unreliable.

**Paths for defect 2:**
1. Re-wire fixed specialists as `AgentTool`s of the coordinator (tool
   calls always return to the caller → the coordinator deterministically
   composes; zoning's schema still binds zoning's own reply). Architecture
   change to Phase-1-ratified wiring → needs human ratification + a
   verification eval-smoke before trusting it (billable).
2. Prompt-level patches steering who speaks last — brittle against the
   exact failure observed; rejected as primary.
3. Accept nondeterminism and re-run until green — unacceptable for a
   video that must be one continuous unedited take.

**Recommendation:** Path 1 + eval-smoke. **Human decides (ratification +
spend).**

**Update (2026-08-21 evening) — re-wiring deployed; eval-smoke gate RED;
new mechanism isolated.** The AgentTool wiring (ADR-004 + addendum fixes)
deployed cleanly and produced ZERO validation crashes — the original B-009
crash mechanism is confirmed fixed. But the 12-case smoke gate failed:
accuracy 3/8 scoreable (4 cases unscoreable: local DNS flaps — B-003 — and
one 81-min hang ending in server disconnect). Per-case diff vs the
2026-08-19 locked baseline shows **4 clean regressions, all
request_info, all with verifier_first_pass=False + retried=True**
(golden-007/-009/-015/-016; baseline OK on all four). Mechanism: the
coordinator now ECHOES the zoning dict as its final reply, and the
groundedness verifier requires byte-exact verbatim quotes — LLM re-typing
corrupts quotes, verifier fails first pass, and the critique-retry
degrades findings to request_info. The verifier is working as designed;
the echo is the defect. (Predicted as RISK by the pre-deploy verification:
"the coordinator's echo is now the single point of parse".)

**Final status 2026-08-21 (STOPPED, resume Tuesday):** deterministic
composition + deterministic input both deployed. Measured across two gated
runs: groundedness 0.67→1.00 (stable), citation P/R 0.96/1.00 (best ever),
leaks 0, crashes 0, network losses 0 — both fidelity regressions
STRUCTURALLY FIXED. Decision accuracy 0.42→0.50, still below the 0.85 gate
and the old wiring's 11/12 on this subset. Remaining misses are the
fact-hinged borderline set (003/004/007/009/015 churn between outcomes;
cannabis 012 is the known baseline miss, 550s of retries). Hypotheses for
Tuesday, in order: (1) zoning's effective context shape under the private
Runner differs subtly from the node path despite identical input text
(include_contents semantics — diff the actual LLM request via trace);
(2) decision-rule prompt interacts with the tool-call framing;
(3) Pro-at-decision-step lever (roster now open) as measured ablation.
NO further spend today per the human's ruling. Everything committed;
this entry + FAILURES.md F12 are the cold-start handoff.

**Original proposal record — deterministic
composition** — specialist/consult tools stash their validated dicts into
session state; an after_agent_callback composes the final reply in code
(intake verbatim / zoning verbatim / findings+missing_capability), making
quotes byte-exact by construction for BOTH eval and demo paths. LLM
routes; code composes. Design being verified against ADK source by a
3-agent read-only pass before ratification + spend ask.

## B-008 — Local terraform.tfstate truncated to 0 bytes — RESOLVED 2026-08-21

**Resolution:** Human ran the one-line restore (Path 1). Verified: state file
is a byte-exact match of the backup (106,633 bytes, serial 120); `terraform
plan` against it shows exactly `1 to add, 0 to change, 0 to destroy` — the
already-live `caseflow_registry_read_interim` grant awaiting adoption into
state; the three destroyed east resources refreshed away cleanly. The
adoption `apply` is pending (agent sandbox blocks terraform apply; the
command is in PROGRESS.md for the human — it makes no real-world change).
**Lesson carried forward:** a Terraform run that exits non-zero at the END
of an apply is treated as a state-integrity event, not display noise —
check the state file immediately.

**Symptom (2026-08-21):** `infra/terraform/terraform.tfstate` is 0 bytes
(timestamp matches the tail of the east-teardown apply, which exited 255 —
that exit code was a real state-write failure, not display noise as first
assessed). `terraform plan` therefore proposes creating all 66 resources
from scratch. **No apply was run against the empty state — caught at plan.**

**Recovery assets:** `terraform.tfstate.backup` (106,633 bytes, serial 120,
29 resources, valid JSON — verified) was written seconds before the
truncation and reflects the world minus the three already-destroyed east
resources. A second copy is parked in the session scratchpad. The build
agent's attempts to restore it (file copy; `terraform state push`) were
blocked by the permission sandbox — restoring state is a human-run step.

**Paths:**
1. Human runs, from `infra/terraform/`:
   `Copy-Item terraform.tfstate.backup terraform.tfstate -Force`
   then the agent runs `terraform plan` (with the registry image var) to
   confirm the only real diff is the already-committed
   `caseflow_registry_read_interim` grant (already applied via gcloud —
   plan should show it as create; apply reconciles state with reality).
   The three east resources will refresh away as already-deleted.
2. `terraform import` of all 29 resources into fresh state — hours of
   error-prone work; strictly worse.

**Recommendation:** Path 1 — one command, then the agent reconciles.
**Human acts (one line); agent verifies after.**

**Interim consequence honestly recorded:** the approved datastore.viewer
grant for sa-caseflow was applied via gcloud instead of Terraform (directive
6 manual-unblock clause) — the TF resource is committed, so reconciliation
is automatic once state is restored.

## B-007 — Cloud Run URLs unroutable at Google's edge (OPEN; platform anomaly)

**Symptom (2026-08-20):** `civicnexus-registry` deploys Ready
(CONDITION_SUCCEEDED, healthy container, uvicorn serving, both default URLs
present in the v2 API object, ingress ALL, GA stage) — yet BOTH its run.app
URLs return Google's generic edge 404 to anonymous AND authenticated
callers, from the developer machine AND from inside GCP (Cloud Build probe).
Full delete+recreate via Terraform did not change it. Every controllable knob
verified correct; the failure is in Google's frontend routing registration
for this fresh project.

**Paths:**
1. Wait (edge registration anomalies on new projects have resolved in
   hours in the wild) while building everything that doesn't need the URL —
   deny test, per-resource IAM, demo scripts written against the HTTP API.
2. If still dead after ~a day: interim fallback where demo drivers use the
   RegistryStore library directly against Firestore (human-side ADC), and/or
   the coordinator toolset gets a Firestore read path — an architecture
   deviation (bypasses the service policy boundary) that would need a human
   ruling per the Working Agreement.

**Recommendation:** Path 1 today; escalate to the human with Path 2 options
if unresolved. **Nobody acts yet; re-check scheduled.**

**Update (2026-08-20 evening):** still 404 after ~5h. A cheap second-service
diagnostic was offered and the human declined it (cost prudence after the
first budget alert) — the wait-path holds. Everything hot-add-shaped is
built and committed (demo script, matrix hook, make target) so the demo is
runnable within minutes of the edge healing.

**Ruling (2026-08-21, human):** "Try second region, else Firestore-direct."
Executed:
- Second region: identical service deployed to **us-east1** via Terraform
  (`registry_east_enabled`). Its run.app URL returned the SAME generic edge
  404 (anonymous and authenticated). Conclusion hardened: the anomaly is
  **project-wide**, not regional. East service destroyed same day (zero
  residual cost).
- Fallback active: **Firestore-direct interim.** `REGISTRY_MODE=firestore`
  makes the coordinator toolset read `registry_agents` directly
  (`status == "APPROVED"` filter in the query — the tool-poisoning defense
  is unchanged), and `demo_hotadd.py` registers/approves via the
  RegistryStore library under the human's ADC identity, preserving the
  PENDING→APPROVED lifecycle, guards, and audit fields. Unit-tested
  (dispatch + query-filter tests). Honest deviation cost: the Cloud Run
  policy boundary (per-principal invoker IAM) is bypassed for reads;
  Firestore has no row-level IAM, so the read grant is datastore-wide
  (§6.1 already acknowledges this limitation). Reverts to the HTTP path
  (flip env var, redeploy) the moment Google's edge routes the service.
  Recorded in ADR-003 addendum.

**Status: fallback ruled and implemented; blocker remains OPEN against
Google's edge** (the registry service stays deployed; re-probe before
Phase 6 managed-mode work).

## B-006 — Decision-accuracy gate red: fleet measures 65–80% vs the ≥85% §9.4 gate (OPEN, by design honest)

**Symptom:** Five full PermitBench runs (2026-08-19, 20 cases each, live stack):
80% → 70% (same config: run variance) → 80% (temp 0 + ordered decision rule) →
65% (cross-reference clause — regression, reverted) → 70% (final locked
config). Groundedness 90–100% and citation P/R ~0.90–0.95 throughout; leaks 0.
The failure mode is decisions, not law: dominated by over-asking
(request_info where the code as stated already decides), plus one
wrong-section approval (cannabis case citing the ADU section — verbatim quote,
inapplicable statute).

**Paths:**
1. Keep prompt-tuning: measured to be whack-a-mole at n=20 single runs; the
   third variant regressed 15 points. Diminishing and statistically muddy.
2. Proceed with the roadmap: Phase 5's groundedness verifier adds the
   entailment check (catches wrong-section citations) and the
   critique-and-retry loop (§7.3) that directly targets over-asking;
   per-agent retrieval improvements land with the Phase 3 fleet split.
   Track this blocker; re-measure after each.

**Recommendation:** Path 2 — the thresholds stay untouched (prime directive
9), the gate stays visibly red in every eval report until the system earns
it. **Human decides at the Phase 2 gate whether to advance with this open.**

**Addendum (2026-08-19, evening):** After the verifier landed (runs 6–7:
stable 80%, groundedness 100%, zero crashes), the remaining approved lever —
upgrading the zoning reviewer to a Pro-tier model — was probed and is
**unavailable on this project**: every Pro and newer-Flash variant returns
HTTP 417 on the global endpoint; the project's roster is exactly
gemini-3.5-flash and flash-lite. The accuracy ceiling is therefore partly
bounded by the model roster available to a fresh personal GCP project.
Optional non-blocking human action: request expanded model access via the
console (typically takes days). The three remaining misses stay documented;
ensemble voting remains the one untried lever (expected value ≈ one marginal
case, does not address the consistent misses).

**Addendum 2 (2026-08-21): the roster constraint above is STALE.** After the
human found Pro cards in Model Garden, a fresh max-1-token probe per
candidate on the global endpoint measured: `gemini-2.5-pro` AVAILABLE,
`gemini-3.1-pro-preview` AVAILABLE, `gemini-3.6-flash` and
`gemini-3.7-flash` AVAILABLE (control `gemini-3.5-flash` fine;
`gemini-3-pro-preview` and `gemini-3.1-pro` are 404 — nonexistent IDs, not
denials). Exact claim: these models each returned one successful generation
on 2026-08-21; nothing is claimed about quota depth, latency, or eval
accuracy. The Pro-at-decision-step lever is therefore AVAILABLE for the
Phase 5 re-measurement — as a costed proposal with per-run OK (eval spend
rule), not before. Phase discipline holds: no model changes mid-Phase-3.

## B-005 — "No traces from the hello agent" — RESOLVED 2026-08-18 (was a read-path gap, not a write failure)

**Resolution (human console check at the gate):** Trace Explorer shows 24 spans
across all three deployed instances — `invoke_workflow` → `invoke_agent` →
`call_llm` → `generate_content gemini-3.5-flash` — including the instances
deployed via mechanisms I had scored as "failed". Tracing was working all
along. The false negative: **OTel-native spans do not surface through the
legacy Cloud Trace v1 `traces.list` API**, which is what the polling scripts
queried. Console evidence (span IDs, timings, the four Error spans from the
regional-404 run at 17:27 IST) is recorded in PROGRESS.md.

**Two lessons carried forward:**
1. Never conclude "no traces" from the v1 API again; verify in Trace Explorer
   or a modern query surface.
2. Runtime logs show partial instrumentation only: "Unable to import
   GoogleGenAiSdkInstrumentor … Make sure to install google-adk[otel-gcp]".
   Phase 1 agent requirements must include the **`google-adk[otel-gcp]`**
   extra for full HTTPX/gRPC/GenAI-SDK spans.

## B-004 — Repo lives inside a OneDrive-synced folder — RESOLVED 2026-08-18

**Resolution:** Human uninstalled OneDrive entirely, so
`C:\Users\danis\OneDrive\Pictures\CivicNexus` is now a plain local folder with
no sync agent touching `.git/` or `.venv/`. No move needed. Repo will be
connected to a private GitHub remote (human creating it) as the off-machine copy.

## B-003 — Flaky network during tool installs (worked around)

**Symptom:** GitHub and CDN downloads intermittently reset/time out on this machine.
Terraform installed after retries (`terraform 1.15.8` via scoop). The gcloud SDK
zip download failed three times (scoop extras bucket clone reset twice; direct
`dl.google.com` download truncated twice).

**Paths:**
1. Human installs gcloud via the official Windows GUI installer (recommended — it
   also offers the login step a newcomer needs anyway).
2. Keep retrying the silent zip install from this session.

**Recommendation:** Path 1 — installer link is in the GCP setup guide given to the
human on 2026-08-18. **Human acts.**

## B-002 — GCP prerequisites not yet available (expected at this stage)

**Symptom:** No `PROJECT_ID`, no billing-enabled project, no `gcloud auth
application-default login` on this machine. `make bootstrap`, agent deploy, and
`make smoke` are blocked until these exist. Phase 0 cannot exit without them.

**Paths:**
1. Human follows the GCP setup guide (project + billing + auth), then build resumes.
2. None — this is inherently a human step (account ownership, payment method).

**Recommendation:** Path 1. **Human acts**; guide provided 2026-08-18.

## B-001 — Hackathon credits not applied; personal billing instead (decision record)

**Symptom:** The $150 hackathon credit form was not used; the human decided on
2026-08-18 to pay with personal money.

**Paths:**
1. Proceed on personal billing with the existing cost guard (budget alerts at
   $50/$100/$140, Flash-only models, `min-instances=0`, evals nightly not per-push).
2. Still attempt the credit form before its Aug 28 12:00 PM PT deadline if eligible.

**Recommendation:** Path 2 if eligibility allows (free money, deadline is before
freeze) — otherwise Path 1 unchanged. The cost guard stays regardless of who pays.

**Update (2026-08-21):** Human submitted the $150 hackathon credit form (a
week ahead of its Aug 28 deadline); arrival expected ~Mon Aug 24. Until the
credit is VISIBLE on the billing page, nothing changes: personal money is
still what's being spent, so the eval-spend rule, per-run OKs, push
batching, and the ₹13,000 ceiling all stay exactly as they are. When it
lands: alerts track gross spend, so thresholds behave the same; the Phase 5
full-eval budget conversation gets easier.

**Run 4 (2026-08-21 night): baseline-parity payloads deployed; gate RED 0.42; demo auto-skipped (no wasted spend). Payload-shape hypothesis FALSIFIED. Fidelity stable (groundedness 1.00 x3, citations 0.96/1.00). Tuesday order: (1) strip framework identity SI block via before_model_callback (audit-isolated suspect, ~5-line change); (2) Pro-at-decision ablation; (3) revert-hybrid fallback (proven 80%).**

**Run 5 (identity-strip): RED 0.50. Citations now perfect (1.00/1.00), groundedness 1.00 x4 � fidelity fully solved. Both cheap suspects falsified. Tuesday: go STRAIGHT to the revert-hybrid (proven-80% transfer wiring for evals + deterministic demo-only composition) � highest-confidence path (~85-90%) � with the Pro-at-decision ablation as the accuracy play on top. Note: one 2518s case with ServerError retries; baseline smoke subset itself may carry variance (B-006 measured 65-80% swings).**

**Variance-measurement plan (2026-08-25, PRE-COMMITTED before data): two smoke runs on the restored sub_agents wiring (registry-era instruction � NOT byte-identical to the Aug-19 0.92 config; scoped per evidence-precision). Decision rule: SHIP-OLD only if BOTH runs >=9/12; straddling 9/12 -> one more run; both <=8/12 -> old wiring is not better, ship deterministic wiring + demo. A run with >2 errored cases is INVALID (environment, not wiring) and re-runs. Registry preflight: zero APPROVED cards verified before run 1. Per-run results archived.**

**MEASUREMENT VERDICT (2026-08-25): old wiring run1 10/12 (0.83), run2 9/12 (0.75) - both >=9/12 -> SHIP-OLD per pre-committed rule. Deterministic wiring: 0.42-0.50 x3. Old wiring costs ~7x tokens/run (633-655k vs ~87k) - goes in eval report cost table. Groundedness 1.00 on BOTH wirings post-fixes. Demo on old wiring = bounded-retry plan for exit proof; video-day reliability revisited at Phase 7 (hybrid preserved at tag).**
