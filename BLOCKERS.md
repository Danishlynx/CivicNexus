# BLOCKERS

Active blockers and risks, newest first. Format per CLAUDE.md: symptom, candidate
paths, recommendation, who acts.

---

## B-005 — No traces reach Cloud Trace from the deployed hello agent (Phase 0 exit blocked on this alone)

**Symptom:** `make bootstrap`, `make deploy`, and `make smoke` all PASS — the
agent answers queries end to end — but zero traces appear via the Cloud Trace v1
API (filtered and bare list both empty, polled repeatedly over ~40 min). All
three documented tracing mechanisms were tried empirically on 2026-08-18:
(1) SDK `AdkApp(enable_tracing=True)`, (2) the documented telemetry env vars
(`GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` etc. — confirmed present on the
instance spec), (3) ADK CLI `--otel_to_cloud` on a source-built instance. Agent
logs show healthy request handling and no OTel init lines or export errors.

**Paths:**
1. Human opens the console — both the Trace Explorer
   (https://console.cloud.google.com/traces/list?project=civicnexus-hack26) and
   the Agent Engine playground/observability tab for instance 7337306624207355904
   — spans may exist in a store the v1 list API doesn't surface.
2. Instrument our own OTel export in Phase 1 services via `libs/otel` (planned
   anyway per ARCHITECTURE §8): direct `opentelemetry-exporter-gcp-trace` export
   demonstrably lands in Cloud Trace and does not depend on the platform's
   auto-tracing, which may simply be broken/moved on the current runtime.

**Recommendation:** Path 1 at the gate (2 minutes, resolves whether this is a
write problem or a read problem), then Path 2 regardless — our architecture
requires one trace per case rooted at intake, which is our instrumentation, not
the platform's. **Human checks console; build continues on Path 2 in Phase 1.**

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
