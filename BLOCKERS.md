# BLOCKERS

Active blockers and risks, newest first. Format per CLAUDE.md: symptom, candidate
paths, recommendation, who acts.

---

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
