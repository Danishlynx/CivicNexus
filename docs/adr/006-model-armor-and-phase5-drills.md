# ADR-006: Model Armor integration and Phase 5 drill architecture

- **Status:** **ACCEPTED 2026-08-26** (human: "do it all", ratifying asks 1-5
  after the B-010 sitting). Deltas recorded below under "Ratification record".
- **Date:** 2026-08-26 (amended same day after a 4-refuter adversarial pre-spend
  audit: 9 blockers / 20 majors, all incorporated below; audit record in the
  session task log)
- **Deciders:** human + build agent

## Context

Phase 5 ("Armor + drills") exit criteria (§11): Model Armor wired at all four
screening points (§6.3); adversarial cases added; watchdog + verifier complete;
DLQ replay exercised; `make demo-injection` passes; injection block 15/15;
ablation numbers captured.

Framing, binding for every doc, log line, and claim this phase: all adversarial
artifacts are synthetic drill fixtures that exist solely to validate
CivicNexus's own screening guardrails — defensive eval-harness content,
confined to the drill path, targeting nothing external.

Live-docs verification (2026-08-26, prime directive 10; source URLs in the
Phase 5 research record) established facts that force decisions:

1. Model Armor is GA (v1) with full support in us-central1, **but sanitize and
   template operations work ONLY on the regional REP endpoint**
   `modelarmor.us-central1.rep.googleapis.com` — the default host serves only
   floor settings and 404s sanitize. Any default-endpoint SDK usage
   hard-fails. This is exactly the F14 failure class.
2. The standalone API **returns verdicts; it does not block**. Blocking is the
   caller's job (`filterMatchState: MATCH_FOUND` → our pipeline quarantines).
3. Sensitive-data **redaction is not built in**: `sdpSettings.basicConfig` only
   inspects/flags; redaction requires separate DLP template resources.
4. Limits: 4 MB max file; 65,536-token PI/jailbreak cap; oversize content
   yields per-filter `executionState: EXECUTION_SKIPPED` — silently unscreened
   unless the caller walks every filter's executionState.
5. Pricing: free to 2M tokens/month, then $0.10/M — Phase 5 armor spend ≈ $0.
6. `google_model_armor_template` exists in the pinned provider (versions.tf
   floor 6.43 was pinned for this); `modelarmor.googleapis.com` is enabled.

Standing constraints: ADR-005's HARD CONSTRAINT (measured eval path
byte-identical; runner.py / verify.py / agent_client.py / permitbench schema
+ loader are measurement instruments); empty-registry eval invariant;
one-retry-layer-per-domain budget; warmup gates; per-run spend OKs; quota-quiet
windows (F15); [skip ci] discipline (CI eval-smoke fires on every push to
main). B-010: terraform.tfstate truncated — every apply is queued behind the
human's recovery session (D16).

Irreversibility: screening placement, the gate-denominator definition, the
eval-composition claim, and the public security story are expensive to walk
back after the Aug 29 freeze.

## Decisions

**D1 — Screening lives driver/harness-side at all four §6.3 points; zero
engine redeploy.** Point 1 (inbound content) screens in drivers before any
engine call via `sanitizeUserPrompt`; point 2 (worker output before verifier)
screens between `ReviewFinding` validation and `verify_finding` via
`sanitizeModelResponse`; point 3 (letter drafts) screens the draft via
`sanitizeModelResponse` in the new caller; point 4 (memory writes) screens
`facts`/`day0_summary` via `sanitizeUserPrompt` at the top of
`demo_timewarp.write_memories()`. The measured eval path stays byte-identical
and deliberately unscreened; the armor ablation runs isolated (D9). Because
points 2 and 4 modify `scripts/demo_timewarp.py`, **its Phase 4 PASS no longer
covers the modified script: one demo_timewarp re-run green (quiet window,
ceiling ~$2) joins the Phase 5 exit evidence before the video.**

**D2 — Client is raw regional REST, env-immune (F14), fail-closed with named
causes (F7).** New module `libs/tools/src/civicnexus/tools/armor.py`:
hardcoded base URL `https://modelarmor.us-central1.rep.googleapis.com/v1`
parameterized only by explicit `project`/`location` kwargs; ADC bearer token;
per-call timeout from the libs/tools table. Verdict parsing walks **every**
filter's `executionState` (EXECUTION_SKIPPED anywhere = unscreened =
fail-closed), checks `invocationResult == SUCCESS`, handles the doubled
`csamFilterFilterResult` key, and reports **per-filter attribution** (which
filter matched, at what confidence). Fail-closed causes: MATCH on a blocking
filter, any EXECUTION_SKIPPED, invocationResult != SUCCESS, HTTP error after
retries, request body > 4 MB — each named in the structured log and the verdict.
New retry row (ADR-005 §3 table, amended by this ADR in the same commit as
armor.py, RUNBOOK updated with an "amended by ADR-006" note): armor client =
2 attempts, transient-only (429/5xx), jittered backoff; no other layer retries
screening. Every other new client this phase (GCS quarantine writer,
IncidentStore Firestore client, drill pull-subscribers) is constructed with
explicit `project=` from the driver's validated PROJECT_ID (id-form, F8) —
no ambient env resolution anywhere.

**D3 — Blocking semantics wording.** Everywhere: content is *flagged by Model
Armor, blocked and quarantined by the CivicNexus pipeline*. Never a claim that
Google blocks server-side.

**D4 — Per-point SDP policy; blocking rides the injection filters.**
Applications legitimately contain applicant PII, so an SDP match on benign
contact data must not quarantine a case. Policy: **pi_and_jailbreak and
malicious_uri are the blocking filters at all four points; SDP basicConfig is
advisory** (recorded in the screening verdict + logs, feeding the §6.6
redactor story) **at points 1–3, and blocking at point 4** (memory facts are
structured non-PII by design — SDP there is a real red flag). The §6.3
"sensitive data → redact" delta stands (detect, not redact; DLP deferred).
The negative canary arm (D10) validates this policy against real content
shapes before ratification of the template config is final; if it shows
surprises, the posture is re-decided with the human before any billed run.

**D5 — One Terraform-managed template.** `google_model_armor_template`
`civicnexus-armor` in us-central1: `pi_and_jailbreak_filter_settings`
**{ENABLED, LOW_AND_ABOVE}** — *amended 2026-08-27; drafted as HIGH, which
measured 0/15. `confidence_level` is the MINIMUM confidence at which the filter
reports, so HIGH is the LEAST sensitive setting despite reading like the
strongest. Each loosening was ratified only against a clean negative arm
(12 controls, 0 false positives at every setting); progression table and the
single characterised holdout are in B-014*; `malicious_uri_filter_settings`
{ENABLED} (no confidence
knob exists — recorded delta); `sdp_settings.basic_config` enabled (advisory
per D4); `template_metadata`: both logging flags true, `enforcement_type
INSPECT_AND_BLOCK` (statement of intent; enforcement is ours per D3). CSAM is
always-on by platform design. No floor settings (terraform destroy does not
reset them — breaks clean teardown/spin-up).

**D6 — Quarantine flow (never silently drop).** On a blocking verdict at any
point: (a) original bytes to
`gs://civicnexus-hack26-docs-quarantine/<case_id>/<doc>`; (b) `Incident`
(new model, `libs/contracts/incidents.py`: incident_id, case_id,
screening_point, per-filter matches, quarantine_uri, traceparent, ts, actor,
status) to Firestore `incidents/` via a new `IncidentStore` (libs/tools);
(c) `CaseStore.transition(case, QUARANTINED, INCIDENT_RAISED, ...)` —
existing machinery publishes the event with the threaded traceparent and the
audit row. QUARANTINED gains human-only exit edges: → IN_REVIEW (re-admit)
and → CLOSED (discard); `test_quarantine_has_no_machine_exit_yet` updated in
the same change.

**D7 — Eval composition (scope ruling ASK #1).** Shipped census: **20
verified standard cases + the adversarial corpus of D8** (15 injection
fixtures + 4 contradictory + 3 out-of-scope + 3 tool-poisoning = 25
adversarial artifacts; ~45 total). The §11 "evals → ~80" (55 standard + 10
long-horizon) is not honestly reachable by freeze: 35 more standard cases at
the Phase 2 five-drafter/five-verifier standard is days of authoring;
long-horizon needs runner mechanics that exist only as the Phase 4 three-arm
proof (cited as exactly that). **Contrary rule quoted for the ruling:**
ARCHITECTURE §11's scope-cut order says "never cut evals or the video" — our
reading is that it protects the eval subsystem's existence and honesty, not
the 80-case headcount; manufacturing 45 unverified cases would violate
evidence-precision. Upon ratification: CLAUDE.md's `eval-full` row is amended
to "~45 artifacts (ADR-006 D7)", the §9.1/§11 deltas are flagged in
BLOCKERS.md per the conflict rule, and the delta paragraph is added to
report.py's template (report.py is not a frozen instrument) so the
regenerated eval-report carries it.

**D8 — The adversarial corpus, by mechanism (fixes the audit's blocker
arithmetic).** Three classes, three proof mechanisms, never conflated:

- **15 injection fixtures** = the 5 §9.1 variant families (white-text PDF,
  PDF-metadata, image-embedded-text*, "system:" framing, fake-authority) × 3
  seeded instances each. These are the **entire denominator of the "injection
  block 15/15" gate**, measured at the screening layer with **per-filter
  attribution: only pi_and_jailbreak or malicious_uri MATCHes count** — an
  SDP match never satisfies the gate. (Delta from §9.1's 5-injection mix
  recorded: same families, 3 seeds each, so the ratified 15/15 number has a
  literal, honest denominator.)
- **4 contradictory-document + 3 out-of-scope cases**: engine-path adversarial
  cases with pipeline expectations (deny / request_info / escalate) — armor
  should NOT flag them and the drill asserts that too (they double as
  negative controls). Their containment is asserted by outcome, reported
  per-category, never counted in the 15/15.
- **3 tool-poisoning cases**: lookalike registry cards in an isolated drill
  (`scripts/drill_tool_poisoning.py`) — asserted as registry-lifecycle
  rejections (unapproved cards invisible to the coordinator toolset;
  machine-quarantine works; human-only clear), never screened content.

All adversarial artifacts live in **`evals/permitbench/drills/`** with their
own `DrillCase` schema module and loader used ONLY by drill_runner — the
measured `schema.py`/`load_all()`/`cases/` are untouched, so `make eval-full`
never sees them and no measured-instrument change is needed for the corpus.
Reported as: "adversarial containment 25/25, by mechanism (injection 15/15
screening-blocked; contradictory/out-of-scope 7/7 correct pipeline outcomes;
tool-poisoning 3/3 registry-rejected)" — with the per-category table in the
eval report.

**D9 — Isolated drill runner + ablations (ASK #2).**
`evals/drill_runner.py` (own loader, own gate check invoked by
verify-phase-5): armor-ON arm asserts the 15/15 injection gate + quarantine
flow + the 7 negative controls; armor-OFF arm (`--armor off`) feeds
**text-carrier variants only** down the normal pipeline (no PDF ingestion
path exists; PDF variants are marked screening-layer-only in the comparison —
stated in compare.py output so the claim never drifts). Ceiling raised per
audit: armor-OFF arm ≤ $12 with a pre-committed per-arm token abort at ~1.2M
cumulative tokens (partial reported honestly). Drill queries use the
eval-driver 4-attempt retry row. **The injection_block gate lives in
drill_runner, NOT in metrics.py GATES** — CI smoke never sees it (§9.4's
"CI merge gate" narrowing recorded: the gate is evaluated per human-OK'd
drill run; CI merge gates remain the non-adversarial trio). The single
measured-instrument change this phase: `evals/runner.py --no-verifier` with
**pinned semantics: verify_finding still runs once in observe-only mode
(recording first-pass/grounding data) but gates nothing and never retries** —
so the §9.5 "hallucinations caught" comparison has data on both arms.
Artifact discipline: every arm archived to evals/archive/ immediately with a
label + config field; the shipping headline results.json is named at run time
(default: the ratified SHIP-OLD smoke pair) and re-copied before the final
report regeneration; `evals/compare.py` emits the comparison table + chart
from archived arms.

**D10 — $0 canary, both directions, before any billed run.**
`scripts/armor_canary.py` (persists per-fixture sanitize responses to
`.deploy/armor_canary_last_run.json` before parsing):

- **Positive arm:** all 15 injection fixtures MATCH on pi_and_jailbreak or
  malicious_uri specifically. Fixture text may be iterated to strengthen
  the *injection* fixtures only — never to make non-injection categories match.
- **Negative arm:** clean control doc, maria/rosa fixtures, 2–3 golden docs,
  a representative ReviewFinding JSON, a sample letter draft, and the exact
  timewarp facts/day0_summary strings — all must come back NO_MATCH on the
  blocking filters (SDP results recorded and reviewed per D4).

Canary-green (both arms) is a printed precondition of demo_injection; **any
fixture regeneration (Gemma or manual) invalidates canary-green and triggers
a $0 re-canary before the next billed step.** *Image-embedded-text: if the
canary refutes it (image screening is Preview), it is substituted with a
text-carrier variant and the delta recorded here (A-12).

**D11 — Fixtures: deterministic-first; Gemma augments after an OK.** The
adversarial templates are authored deterministically NOW ($0): **a separately
seeded Faker instance and an `adv-###` id namespace, append-only after the 20
goldens** — the golden byte-stream is untouched, enforced by a new test
asserting golden-001..020 YAMLs + docs are byte-identical after regeneration,
plus a determinism test (generate twice → byte equality). PDFs:
`Canvas(invariant=1)` (audit-verified byte-identical) with
`pageCompression=0` and the canary drawn as real text so `read_bytes()`
canary search works; dataset tests split standard/adversarial assertions and
use byte-search for PDFs. The BACKLOG-sanctioned Gemma fixture-generation pass
then regenerates injection fixture texts after its own estimate + per-run OK;
the bonus claim is scoped "Gemma-regenerated injection fixtures (N of 15)"
with N from the run log. `reportlab` joins dev dependencies.

**D12 — Circuit breaker is a library; watchdog-complete is scoped (ASK #5).**
`libs/tools/src/civicnexus/tools/breaker.py`: sha256 over (agent_id, tool,
normalized args); 3 identical on one case → open → publish `incident.raised`
(with an explicit drill case_id) + `RegistryStore.change_status(APPROVED →
QUARANTINED, human_actor=False)` — the one machine-permitted registry move.
Unit-tested; exercised against a **dedicated drill card** (never
tree-preservation@1.0.0). **Ask #5 ratifies the §11/§7.2 scoping:**
"watchdog complete" = ADR-005 stream watchdog + this library breaker + its
drill; coordinator embedding, reroute/escalate, and N-incidents aggregation
are Phase 6+ work, recorded as a §7.2 delta in BLOCKERS.md. The verifier side
is complete (§7.3 four steps live since Phase 2; §3.1 "invoked by
coordinator" delta noted — invocation is driver-side, accepted under
ADR-005's frozen engine).

**D13 — DLQ replay drill with real mechanics.** Terraform: subscription
`timer-fired-drill` on `timer.fired` with `dead_letter_policy` (max 5) →
existing `timer.fired.dlq`, **plus the per-subscription
`roles/pubsub.subscriber` grant to the Pub/Sub service agent
(service-<project#>@gcp-sa-pubsub.iam.gserviceaccount.com) — without it
Pub/Sub cannot forward to the DLQ (proven by timers.tf's own demo-sub
pattern); this corrects D17 and is named in ask #3.** Pull subscription
`timer-fired-dlq-replay` on the DLQ topic. The two demo/replay subscriptions
carry a recorded exemption from the §5 every-sub-has-a-DLQ rule
(drill-lifecycle, driver-pulled, no service consumer). `scripts/dlq_replay.py`
(persists envelopes + pull receipts incrementally): publish a synthetic
envelope (unique event_id, minted traceparent) → **nack-until-observed-on-DLQ
under a generous deadline** (max_delivery_attempts is approximate — never an
exactly-5 loop) → republish the ORIGINAL bytes twice → the driver-side
consumer path executes **a defined side effect: a drill-scoped Firestore
write performed only when `record_event_once` returns True** → assert side
effect count == 1 + traceparent byte-equality. PASS line scoped
"driver-side consumer path" (no deployed timer.fired consumer exists — stated
plainly). Runbook: `docs/runbooks/dlq-replay.md`.

**D14 — Letters leg, de-risked (fixes the audit's cold-engine blocker).**
demo_injection's point-3 leg queries the letters engine with a **fixed
determination-shaped JSON request body** (its instruction contract), stream-parses
to `LetterDraftOut`, screens subject+body via `sanitizeModelResponse`, stages
`action.pending_approval`. Gates before the one-go demo: (a) warmup runs
`--engines caseflow,letters`; (b) a **pre-drill letters rehearsal** — one
real draft query (pennies, its own OK) must return schema-valid
LetterDraftOut; if it fails, letters is redeployed hermetically from its
now-existing lock per RUNBOOK (off eval path, safe) and re-rehearsed; (c)
letters query rides the demo-driver 2-attempt row, wall-clock budgeted for a
500s+ leg (the 502s hot-add precedent) under the 600s idle watchdog;
(d) pre-agreed fallback, decided before the billed attempt, never mid-run:
`--skip-letters` scopes the PASS line to points 1/2/4 with point 3 deferred
to the Phase 6 console caller. Evidence wording: the draft is clean by
construction — point 3 demonstrates **"screened (NO_MATCH) and staged"**,
not a block. The BACKLOG letters-engine-deletion offer is parked through
judging (D14 depends on the engine).

**D15 — demo_injection.py, one-go-hardened.** Skeleton (all five new scripts
share it): Windows UTF-8 stdout/stderr reconfigure; env gate; **$0 infra
preflight BEFORE the warmup spend** — (1) sanitize a probe string against the
live template (doubles as propagation probe), (2) write+delete a probe object
in the quarantine bucket, (3) assert the incident-raised-demo subscription
exists, (4) assert zero drill-poison-* cards in the registry — fail fast with
named causes; then warmup gate (caseflow,letters); mint traceparent +
case_id; `_record/_log_step/_persist` to `.deploy/injection_last_run.json`
before any parsing; fixture negative self-check; screen (point 1) → full D6
quarantine flow → structured asserts (quarantine object exists; case
QUARANTINED; incident doc exists; incident.raised consumed on
`incident-raised-demo` with byte-equal traceparent; blocked content never
reached an engine call); letters leg (D14); PASS line scoped per
evidence-precision. Runs in a quota-quiet window; the drill procedure joins
RUNBOOK in the same commit.

**D16 — Infra additions; ONE consolidated human session (ASK #3).**
Terraform: armor.tf (D5 template); docs-quarantine bucket (uniform
bucket-level access, no public access); subscriptions `timer-fired-drill`
(+ the D13 service-agent subscriber grant), `timer-fired-dlq-replay`,
`incident-raised-demo`. Recurring cost ≈ $0. docs-raw/docs-redacted stay
deferred. **Critical path stated plainly: nothing billable in Phase 5 can
start until the B-010 session completes.** The ask bundles into one sitting:
(1) tfstate restore one-liner; (2) the ~5 prepared imports; (3) `terraform
plan` verified to show no timer-resource re-creations; (4) **GCS-backend
migration** (`terraform init -migrate-state`; bucket exists) so a third
truncation cannot burn a build day; (5) the Phase 5 apply.

**D17 — IAM (amended).** One new grant, named per the evidence standard:
`roles/pubsub.subscriber` → `service-<project#>@gcp-sa-pubsub.iam.gserviceaccount.com`
on subscription `timer-fired-drill` — reason: dead-letter forwarding (D13).
Driver-side armor/template/sanitize calls run under the human's ADC (owner);
first 403 stops work and becomes an ask.

**D18 — Tool-poisoning drill lifecycle.** Cards under reserved prefix
`drill-poison-*`; the drill wraps in try/finally deleting exactly its own
card ids; evidence persisted before parsing; eval/demo preflights assert zero
drill cards (D15). demo_reset.py's scope is NOT extended; the drill's own
deletion authority (its prefix only) is named in ask #3 (data-deletion
class). The breaker drill (D12) uses `drill-poison-breaker` as its target.

**D19 — Scope-cut ranking (pre-committed, so compression never decides ad
hoc).** Cut first: (1) Gemma augmentation (bonus-only; deterministic corpus
exists); (2) PDF variants (text-carrier substitution + recorded delta);
(3) drill_tool_poisoning.py (registry governance already evidenced by the
Phase 3 deny test + approved-only query tests; record the §9.1 delta);
(4) compare.py charts (needed by submission, not the gate); (5) breaker.py →
early Phase 6 with an honest "watchdog partially complete" note in ask #5's
terms. **Never cut:** armor client, point-1 screen, quarantine/incident flow,
canary (both arms), demo_injection, the injection corpus + 15/15, one
armor-off arm, one verifier-off arm, dlq-replay.

## Alternatives considered

- **google-cloud-modelarmor SDK** — default endpoint 404s sanitize (F14 class
  as a hard failure); raw REST matches the proven Memory Bank pattern.
- **Engine-side screening** — forces caseflow redeploy (F13 dice), violates
  ADR-005, makes every armor-off ablation a redeploy.
- **DLP-backed redaction now** — extra API/resources/IAM for a capability no
  exit criterion needs.
- **All-15-armor-blocked gate (first draft of this ADR)** — killed by audit:
  arithmetically impossible under its own D8 and only reachable by
  manufacturing the corpus; replaced by D8's per-mechanism design.
- **Adversarial cases inside evals/permitbench/cases/** — killed by audit:
  `make eval-full` loads untagged cases, a required-outcome ValidationError
  in the catch-all kills a billed run with zero evidence; drills directory +
  own loader instead.
- **Growing evals to ~80 by freeze** — manufactured, unverified cases;
  violates evidence-precision.
- **Floor settings** — destroy doesn't reset them; breaks teardown/spin-up.
- **Reusing timer-fired-demo for the DLQ drill** — nack-starves the shared
  demo subscription; dedicated drill subscription instead.

## Consequences

Easier: visible, ~$0 screening; the measured eval discipline survives
untouched; the fortified story (screen → quarantine → incident → audit, with
traceparent continuity) is demonstrable end-to-end; the 15/15 number is
literal and defensible under audit.

Harder / must-not: the security claim stays scoped (driver/gateway-side
enforcement; measured eval path deliberately unscreened — stated in README);
the 15/15 denominator is the 15 injection fixtures, never the mixed
adversarial set; drill subsets never run through the measured runner; SDP is
advisory at points 1–3 by design; demo_timewarp needs a re-proof run after
the screens land; all stage commits carry [skip ci] (or the phase flips
`ci_trigger_disabled`); billed runs only in quota-quiet windows, each on its
own OK.

## Ratification asks (one human session covers all; item 3 includes the
B-010 recovery)

1. **D7 composition ruling** — ship ~45 artifacts (20 standard + 25
   adversarial by mechanism); §11's "never cut evals" clause quoted above
   considered; CLAUDE.md eval-full row amended; BLOCKERS.md conflict flags
   recorded.
2. **Harness sign-offs (evidence-precision rule)** — (a) `evals/runner.py
   --no-verifier` observe-only flag exactly as pinned in D9; (b) NO other
   measured-instrument changes this phase (corpus lives in drills/; the
   injection gate lives in drill_runner).
3. **Infra + B-010 session (D16)** — restore, imports, plan-verify, GCS
   backend migration, then apply: armor template, quarantine bucket, three
   subscriptions, one IAM grant (role + principal + reason in D17); plus the
   drill-poison-* deletion authority (D18). Also in this sitting: verify the
   $150 credit on the billing page (BACKLOG item, overdue since ~Aug 24) —
   the spend plan below assumes nothing about it; and create the Devpost
   DRAFT (category: Fortified Enterprise Fleet, BACKLOG "this week" item).
4. **Spend plan (ceilings; every run individually OK'd, quiet windows):**
   armor canary $0 (both arms); letters rehearsal ≤ $0.50; injection drill
   ≤ $8 (expected ~$1.5); armor-off arm ≤ $12 with the ~1.2M-token abort;
   verifier-off smoke arm ≤ $5; demo_timewarp re-proof ≤ $2; Gemma
   fixture pass ≤ $1. Phase ceiling ≈ $28 (expected ≈ $6–8). Pro-at-decision
   ablation stays a separate costed proposal.
5. **Watchdog-complete scoping (D12)** — §11 satisfied by stream watchdog +
   library breaker + drill; coordinator embedding/reroute/aggregation
   deferred to Phase 6+ as a recorded §7.2 delta in BLOCKERS.md.

## Ratification record (2026-08-26)

Human ratified asks 1-5 ("do it all") after the B-010 recovery sitting. What
that settled, and what changed against the proposal:

- **Ask 1 (D7 eval composition):** ACCEPTED — ship ~45 artifacts (20 verified
  standard + 25 adversarial by mechanism) rather than §11's ~80. CLAUDE.md's
  `eval-full` row is amended accordingly; §9.1/§11 deltas stay flagged as B-011.
- **Ask 2 (harness sign-offs):** ACCEPTED — `evals/runner.py --no-verifier` as
  pinned in D9 (observe-only, gates nothing, never retries) is the ONLY measured
  instrument change this phase. The drill corpus lives in `drills/` behind its
  own loader and the injection gate lives in drill_runner, never in
  metrics.py GATES.
- **Ask 3 (infra + B-010):** DONE, with deltas. State recovered and migrated to
  a **GCS backend** (`gs://civicnexus-hack26-tfstate`, prefix `infra`,
  versioning on). The bucket was created out-of-band with gcloud rather than
  Terraform — a state bucket managed by the state it holds is a bootstrap cycle,
  and the only pre-existing buckets are Terraform-managed and unversioned;
  recorded per directive 6. Two findings during recovery are written up in
  B-010: a plan without `-var registry_image` plans the LIVE registry service
  for destruction, and the timer-fired-demo DLQ subscriber grant had never been
  created, which made `make dlq-replay` unreachable.
- **Ask 4 (spend plan):** ACCEPTED as ceilings. The standing eval-spend rule is
  unchanged and still governs: **every billed run gets its own OK**, in a
  quota-quiet window, with the estimate treated as a ceiling to verify against
  the billing page — never as an assumption.
- **Ask 5 (watchdog scoping):** ACCEPTED — "watchdog complete" = ADR-005 stream
  watchdog + the library breaker + its drill. Coordinator embedding, reroute and
  N-incident aggregation are Phase 6+, recorded as a §7.2 delta in BLOCKERS.

**A-11 RESOLVED empirically the same day:** `google_model_armor_template` exists
in the installed provider (google **v7.44.0**, well above the 6.43 floor) and its
schema was read directly rather than assumed. The schema confirms D5's recorded
delta: `malicious_uri_filter_settings` exposes only `filter_enforcement` with no
confidence knob, while `pi_and_jailbreak_filter_settings` takes both
`filter_enforcement` and `confidence_level`. CSAM is not exposed as a setting —
always-on by platform design, as D5 states.

## Build order (one go; free/local first; commits per stage, all [skip ci])

0. This ADR + ASSUMPTIONS + BLOCKERS conflict flags; **$0 REP reachability
   probe today** (GET templates list under ADC — proves DNS/routing/auth/API
   before B-010 gates anything; result recorded in PROGRESS.md).
1. Contracts: `incidents.py` model; QUARANTINED exit edges; tests.
2. libs/tools: `armor.py` (mocked-HTTP tests incl. per-filter
   EXECUTION_SKIPPED walks), `incidents.py` IncidentStore, `breaker.py`;
   RUNBOOK retry-table amendment in the same commit.
3. Fixtures: drills/ directory + DrillCase schema + 25 adversarial artifacts
   (separately-seeded Faker, adv-### namespace, append-only); gencases PDF
   branch (invariant=1, pageCompression=0); golden byte-identity test +
   double-generation determinism test; reportlab dev dep.
4. Drills + harness: armor_canary.py (both arms), demo_injection.py (D15
   skeleton), dlq_replay.py, drill_tool_poisoning.py (D18 lifecycle),
   evals/drill_runner.py (gate + ablation arms), evals/compare.py, runner.py
   --no-verifier (behind ask #2), report.py delta paragraph, runbooks,
   Makefile real recipes (demo-injection, dlq-replay, verify-phase-5).
5. Terraform: armor.tf + storage + subscriptions + the D17 grant — committed;
   applied only in the ask-#3 session.
6. Full local chain green (ruff, mypy strict, pytest, terraform validate).
   Then the billed sequence, each on its own OK, quiet windows: canary (both
   arms, $0) → letters rehearsal → demo_injection → demo_timewarp re-proof →
   armor-off arm → verifier-off arm → Gemma pass + $0 re-canary if used.
