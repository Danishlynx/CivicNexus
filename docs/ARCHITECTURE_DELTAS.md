# ARCHITECTURE delta log

**Intended location:** `docs/ARCHITECTURE_DELTAS.md`, linked from the README and
from the header of `docs/ARCHITECTURE.md`.
**Status:** FINAL draft for the 2026-08-29 freeze. Compiled 2026-08-28 from
BLOCKERS.md (B-011, B-014, B-015, B-016), ADR-002/003/005/006/007, and
PROGRESS.md; adversarial verification pass applied 2026-08-28 (eight entries
and two notice items added by that pass are marked "surfaced by this log" or
carry their own ratifying records). Every entry cites its ratifying record;
entries without a full record are flagged in the notice block below, never
silently included.

ARCHITECTURE.md v1.0 declares itself the single source of truth and says
"Changes to it happen via an ADR, never by silent drift in code." It contains
no delta-log section or convention of its own; the ratified ADRs and the
BLOCKERS conflict flags (B-011, B-015) are where deltas were recorded as they
happened. This document is the consolidated index of all of them, in spec-section
order, so the README and ARCHITECTURE.md can point at one place.

**Entry format:** spec section → what the spec says → what shipped → why →
ratifying record (ADR / BLOCKERS id + date).

---

## ⚠ Notice block — read first

1. **Two entries are ratification-THIN (human-directed, recorded in
   PROGRESS.md, but carrying no ADR number):**
   - **Δ7 (inbox loop):** the simulated-inbox webhook became a Firestore
     `inbox/` queue fed by a receive-only Gmail IMAP watcher and a clerk-console
     form. Recorded as "human-directed" in PROGRESS (2026-08-28 product-loop
     section); no ADR exists.
   - **Δ24 (Cloud Vision OCR attachment pipeline):** built under the human's
     recorded authorization ("build it all as it was supposed to be and test
     it") with a per-run OK for the live proof, and the API enablement is
     recorded in B-016 and `apis.tf` ("ratified 2026-08-28") — but the
     *feature* has no ADR. Recommend a one-line ratification at the freeze
     declaration, or a short ADR, for both.
2. **Three deltas surfaced by this verification pass carry NO ratifying record
   at all — silent drift caught at the freeze:** the §3.2/§8 BigQuery
   `audit.reasoning`/`evals.results` tables (never built — see the §8 entry),
   Appendix B's `docs/iam-matrix.md` + `scripts/check_iam.py` (never built —
   see the Appendix B entry), and the §3.1 timers micro-delta (Cloud Tasks
   only; no Scheduler job). They need the same freeze-line ratification as
   Δ7/Δ24.
3. **One ratified correction is NOT yet implemented:** ADR-007 D12 (the
   `evals/runner.py` empty-registry preflight that fixes ADR-005's false
   claim, B-015 item 9). Re-verified for this log on 2026-08-28:
   `evals/runner.py` still contains no registry/APPROVED/preflight code.
   ADR-007 marked it "droppable to Phase 7" — it is now a Phase 7 owed item,
   and ADR-005's claim remains false until it lands.
4. **The eval decision-accuracy gate: red through the build, split honestly
   at the freeze.** 65–80% across five full runs (B-006), shipped red and
   unedited on the public `/evals` page; the threshold was never lowered
   (prime directive 9). Freeze-eve artifact observability root-caused a stale
   one-permit-type enumeration in intake (plus an outcome-steering verifier
   critique); post-fix the 12-case smoke subset measured **12/12 three
   consecutive times** (CI smoke gate green), while the same-day full 20-case
   run measured **15/20 (75%) — full-set gate stays RED**, the 8 held-out
   cases at 3/8 with the classic over-ask/over-decide split. All runs and the
   red-era baseline archived under `evals/archive/`. See "Standing red gate"
   below.
5. **Two cited status lines were stale until this pass flagged them (both
   corrected repo-side at the freeze, 2026-08-28):** ADR-005's status line
   still read "proposed — requires human ratification" although its
   ratification is evidenced in substance (the 2026-08-26 telemetry-IAM grants
   are logged as the "ADR-005 ratification ask", human-authorized; the Phase 3
   gate passed "post-ADR-005 hardening"); and B-011's own status still read
   OPEN although ADR-006's ratification record (2026-08-26) closed it. Both
   files now carry the correction, dated 2026-08-28, so this log's citations
   of "ADR-005's frozen-engine constraint" and "B-011 item N" no longer land
   on stale text.

---

## §3 — High-level architecture and components

### Δ1 — §3.1: `console` (Next.js) + `api` (FastAPI) collapse into one image, two services
- **Spec:** two separate components — `console` (Next.js on Cloud Run) and
  `api` (FastAPI on Cloud Run; REST, inbox webhook, signed upload URLs, mints
  approval tokens).
- **Shipped:** ONE FastAPI + Jinja2 package (`services/console/`) deployed as
  TWO Cloud Run services from the SAME image: public reader
  (`civicnexus-console`, `allUsers` invoker, SA holds `roles/datastore.viewer`
  only) and IAM-gated clerk (`civicnexus-console-clerk`, invoker exactly
  `user:danishlynx@gmail.com`). It serves both the clerk HTML and the `api`
  JSON surface. **No separate `api` service exists.** Live URLs:
  reader https://civicnexus-console-wrhx6s33dq-uc.a.run.app ; clerk
  https://civicnexus-console-clerk-wrhx6s33dq-uc.a.run.app .
- **Why:** Next.js was costed at 14–18h with a cliff-edge failure mode (nothing
  demoable until both services deploy and CORS works) against 6–8h for the
  FastAPI path that degrades page by page, with ~1 build day before freeze.
  Jinja2 autoescaping is a security property on a public page rendering
  applicant-controlled strings.
- **Ratified:** ADR-007 D1/D2; B-015 item 1; ratified 2026-08-27.

### Δ2 — §3.1/§6.2: no `gateway` service; gateway-scope reframe
- **Spec:** a `gateway` FastAPI service on Cloud Run as the policy enforcement
  point for all agent↔tool and agent↔agent calls, with a `GATEWAY_MODE`
  managed/selfhosted adapter pair.
- **Shipped:** no `services/gateway` exists and `GATEWAY_MODE` has zero code
  hits (verified 2026-08-28). The gateway's *properties* are enforced by other
  ratified mechanisms: platform IAM enforces identity (per-agent SAs, custom
  least-privilege roles, per-resource engine bindings, the deliberate-deny
  test's audited 403); the registry approval lifecycle rejects unapproved
  targets; Model Armor screening is called directly (driver-side) at all four
  §6.3 points, as §6.2 itself anticipated ("Model Armor is GA and callable as
  an API regardless of gateway mode").
- **Why:** the ratified Phase 3 reframe — "platform IAM enforces identity;
  gateway = policy/screening/audit" — plus ADR-005's frozen-engine constraint;
  the managed bind was never attempted (see Δ20).
- **Ratified:** Phase 3 gate ruling, 2026-08-26 ("gateway-scope reframe
  RATIFIED", PROGRESS); ADR-003 consequence flagged in BACKLOG for exactly
  that gate.

### Δ3 — §3.1: specialist agents composed in-process, not one runtime per agent
- **Spec:** `coordinator`, `intake`, `zoning`, `safety`, `letters` as
  individually listed ADK agents.
- **Shipped:** `civicnexus-caseflow` is one Agent Engine instance carrying
  coordinator + intake + zoning in-process (ADK `sub_agents` wiring); safety,
  letters and tree-preservation run as separate engines with per-agent SAs.
  The AgentTool re-wiring experiment was measured and reverted: the
  pre-committed 2026-08-25 decision rule shipped the old wiring (10/12 and
  9/12 vs 0.42–0.50 for the deterministic alternative).
- **Ratified:** ADR-002 item 4 (Phase 1, "in-process composition per ADR-002
  item 4"); SHIP-OLD measurement verdict pre-committed and executed 2026-08-25
  (B-001 run log / B-009).

### Δ4 — §3.1/§7.3: verifier invoked driver-side, not by the coordinator
- **Spec:** `verifier` is a library "invoked by coordinator".
- **Shipped:** the §7.3 four-step verifier is complete and live since Phase 2,
  but invocation is driver-side (the eval/demo drivers call it), accepted
  under ADR-005's frozen-engine constraint.
- **Ratified:** ADR-006 D12 ("§3.1 'invoked by coordinator' delta noted —
  invocation is driver-side, accepted under ADR-005's frozen engine"),
  ratified 2026-08-26.

### Δ5 — §3.1/§11: dedicated redactor NOT built
- **Spec:** `redactor` component (Gemma via Vertex AI, fallback Cloud DLP)
  stripping PII before logging/embedding/memory writes; §11 Phase 6 "redactor
  in the write path".
- **Shipped:** not built. Compensating controls, all measured: Model Armor's
  `sdp` filter runs at all four §6.3 screening points — advisory (detect) at
  points 1–3, BLOCKING at point 4, memory writes (ADR-006 D4; see Δ11) — with
  `match_state` recorded on every incident; canary leak rate measured 0.0% in
  every eval run and both ablations; synthetic data only.
- **Ratified:** ADR-007 A9 + D10 (deviation ratification, compensating
  controls named); B-015 item 3; ratified 2026-08-27.

### Δ6 — §3.2: `determinations/` never became its own collection
- **Spec:** Firestore collections include `determinations/`.
- **Shipped:** determinations live inside `cases/{id}` via
  `firestore.ArrayUnion` — one read yields the whole case, no joins.
- **Ratified:** B-015 item 8 (recording an existing fact); ADR-007 §7 delta 3;
  ratified 2026-08-27.

### Δ7 — §3.1/§6.2: `api` line items — inbox webhook re-shaped, signed upload URLs cut ⚠ RATIFICATION-THIN (inbox half)
- **Spec:** `api` hosts the simulated inbox webhook and signed GCS upload URLs.
- **Shipped:** *(a)* signed GCS upload URLs CUT — `docs-raw/` and
  `docs-redacted/` buckets do not exist (ratified: ADR-007 §7 delta 6 / D10
  cut list, 2026-08-27). *(b)* The simulated inbox became `InboxStore`
  (Firestore `inbox/`, write-once + claim/finish/fail + startup requeue,
  single-consumer stated honestly) fed by a REAL Gmail inbox via
  `scripts/inbox_watcher.py` (IMAP BODY.PEEK, receive-only per the fixture
  rules — the simulated inbox never sends real email) and by the clerk
  console's "New application" form; one queue, two feeders, one consumer
  driving the proven run_case chain, spend-bounded (`--i-accept-billing`,
  `--max-cases` default 3).
- **Why:** the video's live email→case→citation→human-gate walk; the fallback
  form keeps the take alive through a network flake.
- **Record:** PROGRESS 2026-08-28 "Product loop + curated console
  (human-directed)"; runbook `docs/runbooks/video-inbox-demo.md`. **No ADR —
  flagged in the notice block.**

### Δ — §3.1: timers — "Cloud Tasks + Cloud Scheduler" → Cloud Tasks only
- **Spec:** §3.1's timers row names "Cloud Tasks + Cloud Scheduler" for
  "recheck in N days" wakeups.
- **Shipped:** timers run on Cloud Tasks alone — the Phase 4 time-warp proof
  (honoring `CLOCK_MULTIPLIER`) exercised Cloud Tasks only. The Cloud
  Scheduler API is enabled in `apis.tf`, but no `google_cloud_scheduler_job`
  resource exists anywhere in `infra/terraform` (verified 2026-08-28).
- **Record:** none — previously unrecorded micro-delta, surfaced by this log
  (see notice block item 2).

### Δ — §3.2: "stable chunk_ids" → citation key is file identity
- **Spec:** the corpus is "chunked ~500 tokens with stable `chunk_id`s".
- **Shipped:** retrieval exposes no chunk IDs — `RagChunk` carries only
  `text` + `page_span` (verified in SDK types). The corpus is ingested one
  file per code section (`17.44.NNN`), `source_display_name` is the citation
  key carried in `Citation.chunk_id`, and the verifier string-matches quotes
  against the committed section text in `data/corpus/` — stronger than
  trusting an opaque chunker.
- **Ratified:** ADR-002 item 3 (status: accepted), 2026-08-18; flagged and
  accepted at the Phase 1 gate.

## §5 — Event schema and topics

### Δ — §5: two demo/replay subscriptions exempt from the every-subscription-has-a-DLQ rule
- **Spec:** "every subscription has a dead-letter topic after 5 delivery
  attempts".
- **Shipped:** the two demo/replay subscriptions carry a recorded exemption —
  `timer-fired-dlq-replay` (which reads the DLQ topic itself) and
  `incident-raised-demo` have no `dead_letter_policy` (verified in
  `infra/terraform/armor.tf`, 2026-08-28). Recorded reason: drill-lifecycle,
  driver-pulled, no service consumer. Service-consumed subscriptions keep
  their DLQs, and `make dlq-replay` is proven against the real mechanics.
- **Ratified:** ADR-006 D13 (exemption recorded in the decision text),
  ratified 2026-08-26.

## §6 — Security architecture

### Δ — §6.1: "Google-signed ID tokens (audience-checked) on every internal call" → OAuth access tokens + per-resource IAM on engine↔engine legs
- **Spec:** services verify audience-checked, Google-signed ID tokens on every
  internal call.
- **Shipped:** no ID-token/audience mechanism exists for Agent Engine↔Agent
  Engine (platform fact, live-docs + installed-SDK verified); authorization on
  that leg is `aiplatform.reasoningEngines.query` granted per agent resource —
  the deny-by-default matrix the deliberate-deny test proves with an audited
  403. ID tokens remain the pattern on Cloud Run legs only. A2A-proper was
  spiked and refuted for CLI-deployed ADK 2.7.1 agents; consult uses the
  proven `:streamQuery` transport (human ruling 2026-08-20).
- **Ratified:** ADR-003 decisions 1/3 + the A2A spike ruling; ADR-003 status
  line "ratified by the human 2026-08-20".

### Δ8 — §6.2/§6.4: approval token minted by `ApprovalStore`, verified inside `CaseStore`
- **Spec:** "`api` … mints approval tokens"; side-effect tools require an
  approval token minted by `api`.
- **Shipped:** `ApprovalStore` (`libs/tools`) mints the row
  `{approval_id, case_id, action, target_state, approver, approval_token,
  traceparent, created_at}`; `CaseStore.transition` into ISSUED/DENIED
  verifies the row exists and names THIS case and THIS target — inside the
  single writer, not the caller. Token *consumption* plumbing is deliberately
  NOT built: no send path exists in the codebase to consume one (letters
  stages drafts only). The live proof: the human clerk walk left
  `approvals/apr-ea2cfd823116` naming danishlynx@gmail.com / issue / ISSUED.
- **Ratified:** ADR-007 D3 + A6 (guardrail-strengthening ask); B-015 item 2;
  ratified 2026-08-27.

### Δ9 — §6.2: registry consulted Firestore-direct (`REGISTRY_MODE=firestore` interim)
- **Spec:** the coordinator discovers capabilities via the registry *service*
  behind the policy boundary.
- **Shipped:** the coordinator toolset reads `registry_agents` directly from
  Firestore with the `status == "APPROVED"` filter (tool-poisoning defense
  unchanged), under an interim `roles/datastore.viewer` grant to
  `sa-caseflow`. Honest cost recorded at the time: the Cloud Run per-principal
  invoker boundary is bypassed for reads, and Firestore has no row-level IAM
  (§6.1 already acknowledges this). B-007's edge anomaly later healed; the
  `REGISTRY_MODE=http` revert + grant removal were deliberately deferred at
  Phase 6 (no caseflow/registry redeploy days before the video).
- **Ratified:** human ruling 2026-08-21 ("Try second region, else
  Firestore-direct") + ADR-003 addendum; the deferral of the revert ratified
  via ADR-007 D10 cut list, 2026-08-27. Grant removal condition stands in the
  IAM evidence log ("REMOVE at reversion to REGISTRY_MODE=http").

### Δ10 — §6.3: screening template sensitivity — "high confidence" → `LOW_AND_ABOVE`
- **Spec:** "prompt-injection/jailbreak at high confidence → block".
- **Shipped:** `pi_and_jailbreak {ENABLED, LOW_AND_ABOVE}` on the live
  `civicnexus-armor` template. Context that makes this correct rather than
  loose: `confidence_level` is the MINIMUM confidence at which the filter
  reports, so HIGH is the LEAST sensitive setting despite reading like the
  strongest. At HIGH, the screening drill measured 0/15 on the drill corpus
  (defensive fixtures adv-001..adv-015, built solely to validate our own
  guardrails; they never leave the drill path). Each loosening step was kept
  only because the negative arm stayed clean — across all four measured
  configurations (12 real controls each) the guardrail never once flagged a
  genuine application, letter, determination or memory string.
- **Ratified:** B-014 (measured ladder + both arms, human applied each
  setting); ADR-006 D5 amended 2026-08-27 with the amendment recorded in the
  ADR text.

### Δ11 — §6.3: "sensitive data → redact" → SDP detect-only, per-point policy
- **Spec:** sensitive data → redact.
- **Shipped:** SDP `basic_config` runs in DETECT (advisory) mode at screening
  points 1–3 and BLOCKING at point 4 (memory writes), because applications
  legitimately contain applicant PII and an SDP match on benign contact data
  must not quarantine a case; redaction proper needs DLP, deferred with Δ5.
- **Ratified:** ADR-006 D4 ("the §6.3 'sensitive data → redact' delta stands
  (detect, not redact; DLP deferred)"); ratified 2026-08-26.

### Δ12 — §6.3 point 3 closed by the drill harness, not a console caller
- **Spec/plan:** Phase 5 recorded letter-draft screening (point 3) as deferred
  to the Phase 6 console caller.
- **Shipped:** point 3 was closed by one billed run of
  `make demo-injection DEMO_ARGS=--with-letters` — the letters leg screens the
  draft at `letter_draft`; measured live 2026-08-28 (draft screened NO_MATCH
  and staged as `action.pending_approval`). All four §6.3 points now hold live
  measurements (points 1/2/4 via demo_timewarp/demo_injection, point 3 via the
  letters leg).
- **Ratified:** ADR-007 D11 + spend ask A7 (ratified 2026-08-27); Phase 5 gate
  default recorded in PROGRESS; A7 closure recorded 2026-08-28.

## §7 — Reliability

### Δ13 — §7.2: "watchdog complete" scoped
- **Spec:** coordinator hashes worker calls; three identical hashes open a
  circuit, reroute/escalate; N incidents quarantine the agent version.
- **Shipped:** ADR-005 stream watchdog + a library circuit breaker
  (`libs/tools/.../breaker.py`: 3 identical call-hashes on one case → open →
  `incident.raised` + machine-quarantine of the registry card) + its drill.
  Coordinator-embedded hashing, reroute/escalate, and N-incidents aggregation
  are deferred to Phase 6+ (embedding requires a caseflow redeploy, which
  ADR-005 forbids without the parity gate).
- **Ratified:** ADR-006 D12 / ask 5, ratified 2026-08-26; B-011 item 3.

## §8 — Observability

### Δ14 — §8: no Looker Studio dashboard
- **Spec:** a Looker Studio dashboard over BigQuery, appearing in the video.
- **Shipped:** never built. The console's `/evals` page renders
  `docs/eval-report.md` unedited — whatever its gate status (it displayed
  "Gates: FAIL — decision_accuracy 0.750 < 0.85" for most of the build; green
  since the 2026-08-28 defect fix). The README must not imply a dashboard
  exists.
- **Ratified:** B-015 item 7; ADR-007 §7 delta 7 / D5; ratified 2026-08-27.

### Δ — §3.2/§8: BigQuery `audit.events`/`audit.reasoning`/`evals.results` → one log-sink dataset; reasoning/evals tables NOT built ⚠ RATIFICATION-ABSENT
- **Spec:** §3.2 names BigQuery tables `audit.events`, `audit.reasoning`, and
  `evals.results`; §8 says the reasoning audit ("redacted rationale + verifier
  report") persists to `audit.reasoning`.
- **Shipped:** one `audit` dataset fed by a `jsonPayload.audit=true` log sink
  with partitioned log tables (`infra/terraform/audit.tf`) — not a named
  `events` table. No `audit.reasoning` or `evals.results` exists anywhere
  (zero repo hits outside spec text, verified 2026-08-28). Reasoning and
  verifier reports persist inside `cases/{id}`; eval results are repo
  artifacts (`evals/results.json`, `evals/archive/`, `docs/eval-report.md`).
  ADR-005 §6.3 additionally discloses the sink's blind spot: driver-side runs
  emit no in-GCP stdout, so local-script actions leave no BigQuery audit rows.
  Same rule class as Δ14: the README must not imply these tables exist.
- **Record:** none ratifies the drift — surfaced by this log; needs a
  freeze-line ratification alongside Δ7/Δ24 (see notice block item 2).

## §9 — Evals (PermitBench)

### Δ15 — §9.1/§11: eval composition ~80 → ~45 artifacts
- **Spec:** ~80 cases (55 standard, 15 adversarial, 10 long-horizon); §11
  "adversarial cases added (evals → ~80)".
- **Shipped:** ~45 artifacts — 20 verified standard cases + 25 adversarial by
  mechanism (15 injection drill fixtures + 4 contradictory + 3 out-of-scope +
  3 tool-poisoning). The 10 long-horizon cases were not authored; the Phase 4
  three-arm memory proof is cited as exactly that, not as eval cases.
  CLAUDE.md's `eval-full` row was amended upon ratification. Reasoning of
  record: 35 more standard cases at the Phase 2 five-drafter/five-verifier
  standard is days of authoring; manufacturing 45 unverified cases would
  violate evidence-precision; the "never cut evals" clause is read as
  protecting the subsystem's existence and honesty, not the headcount.
- **Ratified:** ADR-006 D7 / ask 1, ratified 2026-08-26 ("do it all");
  B-011 item 2.

### Δ16 — §9.1/§9.4: injection-gate denominator redefined honestly
- **Spec:** §9.1's mixed 15-case adversarial set; §9.4 "injection block 15/15".
- **Shipped:** the gate is measured over 15 DEDICATED injection drill fixtures
  (the 5 §9.1 variant families × 3 seeds, ids adv-001..adv-015) with
  per-filter attribution — only `pi_and_jailbreak` or `malicious_uri` MATCHes
  count; an SDP match never satisfies the gate. Contradictory/out-of-scope
  cases prove containment by pipeline outcome; tool-poisoning by registry
  rejection (3/3 lookalike cards forced PENDING, invisible to the approved-only
  query, machine approval refused). The pre-audit draft would have
  manufactured the number over the mixed set; this is the honest form.
- **Ratified:** ADR-006 D8, ratified 2026-08-26; B-011 item 1.

### Δ17 — §9.1: image-embedded-text family substituted with a text carrier
- **Spec:** §9.1's five injection variants include "image-embedded text".
- **Shipped:** the image family was substituted by `quoted_attachment` (text
  carrier) and the generator's image branch removed, because PDF
  byte-screening was MEASURED not to read text inside embedded raster images
  (a rung-4-strength control string matched as page text and metadata but not
  as an embedded raster). A-12 pre-registered exactly this refutation and
  ADR-006 D10 ratified the substitution in advance. See Δ18's coverage
  statement for how the intake path now compensates.
- **Ratified:** ADR-006 D10/A-12 (substitution clause); measured and executed
  2026-08-27 (B-014 root-cause section).

### Δ — §9.3/§11: letters-quality rubric scoring CUT
- **Spec:** letter quality scored by the Vertex AI evaluation service against
  a small rubric (clarity, tone, accuracy) — advisory, not gating; second in
  §11's sanctioned scope-cut order.
- **Shipped:** never built; cut in order — between the managed-gateway adapter
  (Δ20, first cut) and console polish (cut third, later overridden — C5).
  Zero rubric-scoring code in the repo (verified 2026-08-28).
- **Ratified:** ADR-007 D10 cut list ("Letters-quality rubric — second in the
  cut order"), ratified 2026-08-27.

### Δ18 — §11 Phase 5 exit: "injection block 15/15" → measured **14/15** (never quoted bare — B-014 reporting rule)
- **Spec:** exit criterion "injection block 15/15", authored under assumption
  A-9 (that domain-phrased drill fixtures reach a HIGH-confidence match) —
  A-9 was refuted by measurement.
- **Shipped:** **14/15**, stable across three consecutive runs with the same
  single miss. Per the binding reporting rule, the number always ships with
  ALL of the following:
  - **Setting:** `pi_and_jailbreak {ENABLED, LOW_AND_ABOVE}` on the live
    template (see Δ10).
  - **Progression (both arms measured at every step):**

    | Setting | Fixtures | Positive arm | Negative arm |
    |---|---|---|---|
    | HIGH | original | 0/15 | 12 controls, 0 false positives |
    | MEDIUM_AND_ABOVE | original | 2/15 | 12 controls, 0 false positives |
    | MEDIUM_AND_ABOVE | strengthened | 8/15 | 12 controls, 0 false positives |
    | **LOW_AND_ABOVE (shipped)** | **strengthened** | **14/15** | **12 controls, 0 false positives** |

  - **Two levers, reported separately:** (1) sensitivity, loosened in two
    measured steps and kept at each only because the negative arm stayed
    clean; (2) drill-fixture strength, rewritten to the requirement a
    sensitivity ladder measured (not to whatever made the gate green).
  - **The characterised holdout, deliberately not tuned away:** adv-001 sits
    at a 46% injection share between two same-family siblings at 45% and 47%
    that both pass, and its instruction matches when screened standalone; the
    dilution boundary was measured non-monotonic (MATCH at 63%, NO MATCH at
    54% and 46%, MATCH again at 37%). A fixture failing between two passing
    fixtures at essentially the same ratio is boundary behaviour, not a
    defect; editing it until it passed would fit noise.
  - **Coverage statement (CURRENT as of 2026-08-28):** PDF byte-screening
    reads page text and all three document-info entries (/Subject, /Keywords,
    /Author — each measured individually) but does NOT read text rendered
    inside embedded raster images (A-12). **However, on the intake path this
    blind spot is now closed:** every allowlisted intake attachment
    (PNG/JPEG/PDF) is transcribed by deterministic Cloud Vision OCR and the
    extracted text is RE-SCREENED as plain text — the screen B-014 measured
    most sensitive (11/15 drill-fixture instructions match as bare text vs
    2/15 inside PDFs) — live-proven 2026-08-28 (see Δ24). The screening-layer
    gap statement stands for raw PDF byte-screening itself; the drill corpus
    contains no image-carrier fixture (Δ17).
- **Ratified:** B-014 FINAL 2026-08-27; Phase 5 gate passed 2026-08-27 with
  the human's explicit "i accept 14/15"; the drill runner and canary default
  `--expect 14` so a run demanding 15 fails for a known reason.

### Δ19 — §9.4: CI merge-gate narrowing — the injection gate lives in the drill runner
- **Spec:** §9.4 lists "injection block 15/15" among CI merge gates.
- **Shipped:** the injection gate lives in `evals/drill_runner.py`, evaluated
  per human-OK'd drill run — never in `metrics.py` GATES, so CI smoke never
  sees it. CI merge gates remain the non-adversarial trio (decision accuracy,
  groundedness, leak rate). This keeps billed adversarial screening runs under
  the per-run-OK spend rule rather than on every push.
- **Ratified:** ADR-006 D9 ("§9.4's 'CI merge gate' narrowing recorded"),
  ratified 2026-08-26.

### Δ — §9.4/§13: CI cadence — smoke on every push to main; no nightly full run
- **Spec:** §9.4 "PRs run the 12-case smoke subset; `main` runs nightly full";
  §13 repeats "eval smoke on PRs, full runs nightly only".
- **Shipped:** the smoke subset fires on **every push to main** (recorded in
  ADR-005 §5.2: "CI eval-smoke — fires on every push to main"), and no
  nightly full run exists — full runs are billed and require the human's
  per-run OK under the CLAUDE.md eval-spend amendment. Δ19 narrows what the
  CI gate contains; this entry records when it runs.
- **Ratified:** the CLAUDE.md Working Agreement eval-spend rule (added
  2026-08-20, ratified by the human) is the ratifying record for the cadence
  change; the shipped trigger is recorded in ADR-005.

### Standing RED gate (not a deviation — the threshold is untouched)
- **§9.4 decision accuracy ≥ 0.85: FAIL at 75.00%** (12-case smoke of record,
  2026-08-25; B-006 measured 65–80% across full runs). Groundedness 100%,
  citation P/R 91.67/91.67, leak rate 0 on the same run — the failure mode is
  decisions (over-asking; one wrong-section approval), not law or leaks. The
  gate was never lowered (prime directive 9); it is visibly red in
  `docs/eval-report.md`, on the public `/evals` page, and here. B-006 stays
  OPEN; the human decided at the Phase 2 gate (2026-08-20) to lock the honest
  baseline and advance with it open, reaffirmed at the Phase 3 gate ("CI smoke
  gate stays honestly RED").

### Δ (§9.5 / DoD): ablation charts exported by hand — CLOSED 2026-08-29
- Both §9.5 ablations are measured and tabled in `docs/ablations.md`
  (verifier off/on; Model Armor off/on with the text-carrier-only scope
  stated). `evals/compare.py` still renders **nothing** — matplotlib is not a
  project dependency, and that line survives unchanged in the generated
  report. The DoD item is instead closed by three **hand-authored,
  self-contained SVGs** in `docs/charts/` (accuracy by configuration;
  ablation 1 verifier; ablation 2 Model Armor), each value transcribed from a
  named archived artifact and each chart carrying its own scope caveats and
  source list. Exact claim: the charts exist and are traceable; the *script*
  still cannot draw them, so a matplotlib install remains the only way to make
  this reproducible from `make` rather than by hand.

## §11 / Appendix A — Phase 6 scope

### Δ20 — §11: managed-gateway adapter CUT
- **Spec:** Phase 6 "managed-gateway adapter if access granted".
- **Shipped:** cut — it is the top entry of §11's own scope-cut order; no
  `services/gateway` exists to bind (Δ2); the managed Agent Registry API shows
  "Not enabled" and enabling it is itself a Terraform change plus an apply.
- **Ratified:** ADR-007 D10; B-015 item 4; ratified 2026-08-27.

### Δ21 — §11: "activity feed" delivered as a derived per-case timeline
- **Spec:** activity feed (implying the §5 event stream).
- **Shipped:** a per-case timeline derived from `created_at`, `updated_at`,
  `state`, `determinations[]`, `timers[]` and the case's incidents, labelled
  as derived in the UI. Honest reason: the §5 `case.*`/`review.*`/`action.*`
  topics have ZERO subscribers, so messages are discarded at publish; a real
  global feed would mean adding a persistent append inside `CaseStore._emit`
  — the audited single-writer hot path — on freeze day.
- **Ratified:** ADR-007 D5; B-015 item 5; ratified 2026-08-27.

### Δ22 — §11/Appendix A: `SAFE_MODE` NOT implemented
- **Spec:** `SAFE_MODE` (default on) no-ops all side-effect tools; listed in
  Appendix A; CLAUDE.md prime directive 4 assumes it.
- **Shipped:** zero code hits repo-wide (verified in B-015; re-verified for
  this log 2026-08-28). It is specified as a kill switch over side-effect
  tools that do not exist (no send path anywhere). The console's read-only
  exposure is `CONSOLE_MODE=reader` — deliberately a DIFFERENT name so no
  reader mistakes it for the spec's flag. The property SAFE_MODE protected is
  enforced structurally: the reader SA holds `roles/datastore.viewer` only,
  write routes are not mounted in reader mode, and letters can only stage for
  approval.
- **Ratified:** ADR-007 D4; B-015 item 6; ratified 2026-08-27.

### Δ23 — §11 Phase 6 exit scope: "full case from the UI alone" defined
- **Spec:** exit — "clerk can run a full case from the UI alone".
- **Shipped ruling:** read as PENDING_HUMAN → APPROVED → ISSUED → CLOSED plus
  the QUARANTINED re-admit, with intake EXCLUDED — §3.1 does not list intake
  among the console's responsibilities (it is a webhook, by definition not a
  UI action). Both halves of the exit are done: machine
  (`verify-phase-6`, 18 assertions green ×4 deployed revisions) and human (the
  clerk drove `case-f319c7ccab71` PENDING_HUMAN→APPROVED→ISSUED→CLOSED in a
  browser, leaving `approvals/apr-ea2cfd823116`).
- **Ratified:** ADR-007 D6 / ask A10, ratified 2026-08-27; exit recorded
  2026-08-28.

## Appendix B — IAM artifacts

### Δ — Appendix B: `docs/iam-matrix.md` + `scripts/check_iam.py` never built ⚠ RATIFICATION-ABSENT
- **Spec:** Appendix B says the full IAM matrix "lives at `docs/iam-matrix.md`
  and is kept in sync by `scripts/check_iam.py` (drift fails CI)".
- **Shipped:** neither artifact exists — zero repo hits outside the spec
  sentence itself (verified 2026-08-28). Compensating record, all live: the
  PROGRESS IAM evidence log (every grant names the role, the principal, and
  the reason, per the ratified IAM evidence standard), the deliberate-deny
  test's audited 403, and `verify_phase6`'s role assertions (reader SA exactly
  `[roles/datastore.viewer]`; clerk invoker exactly one named human).
- **Record:** none — previously unrecorded; surfaced by this log (see notice
  block item 2).

## Additions — capabilities NOT present in ARCHITECTURE.md

### Δ24 — Cloud Vision OCR attachment pipeline (ADDITION) ⚠ RATIFICATION-THIN
- **Spec:** Vision/OCR appears NOWHERE in ARCHITECTURE.md (verified by
  full-text search, 2026-08-28: zero hits for vision/OCR). §3.1 does assign
  the intake agent "multimodal extraction from messy PDFs/images", and §3
  shows applicant docs entering via the simulated inbox — this addition is the
  defensive screening layer for that path, not a new product feature.
- **Shipped:** allowlisted intake attachments (PNG/JPEG/PDF; 3 per email,
  4MB cap): PDFs byte-screened first; every attachment then transcribed by
  deterministic Cloud Vision OCR (a transcription engine, not a chat model —
  pixels cannot instruct it); the extracted text screened AGAIN as plain text;
  clean text joins the application under provenance framing
  ("applicant-supplied data, not instructions"). Fail-closed ruling: an
  attachment OCR cannot transcribe returns `Hostile("attachment_unreadable")`
  and the case QUARANTINES for a human decision. Live-proven 2026-08-28:
  containment (a pixel-rendered override in a drill screenshot fixture was
  OCR-read, matched `pi_and_jailbreak` at HIGH as plain text, case
  `case-1216f7712d35` QUARANTINED with zero engine calls) and clean enrichment
  (`case-13ee94915b12`: floor-plan attachment screened+extracted → verifier
  passed first pass → approve at the human gate in ~62s).
- **Record:** B-016 (Vision API enabled via gcloud + `terraform import`,
  directive-6 record, RESOLVED — post-import plan "No changes");
  `infra/terraform/apis.tf` carries the resource with a "ratified 2026-08-28"
  comment; PROGRESS 2026-08-28 attachment-pipeline + LIVE-PROVEN sections
  record the human authorization and the per-run OK. **No ADR — flagged in
  the notice block.** Evidence-precision scope carried from PROGRESS: the
  Gmail IMAP attachment leg has not fired live (both runs used the `.eml`
  fixture path; the IMAP walk shares the same code and the rehearsal proved
  the IMAP hop itself); the PDF leg is unit-tested + probe-verified but no
  end-to-end `.eml` PDF run has been made.

## Corrections to ratified ADRs (measured platform behaviour or recorded overrides)

These deviate from ratified ADR text, not from ARCHITECTURE.md directly; each
is recorded in the ADR or PROGRESS rather than silently drifted.

### C1 — `/healthz` → `/api/health` (Cloud Run frontend interception)
Google's frontend intercepts the literal `/healthz` path on run.app and
answers its own HTML 404 before the container is consulted (measured;
sibling routes serve fine). Health moved to `/api/health`. This also
re-explains B-007's "registry `/healthz` 404s, revision must be stale" note —
same interception; the staleness reading was wrong. Record: PROGRESS
2026-08-28 verify-phase-6 section; correction note embedded in ADR-007 D2.

### C2 — Clerk attribution via `CLERK_SOLE_INVOKER`
Cloud Run validates and CONSUMES the caller's Authorization credential — the
container receives no decodable token (measured with both header patterns).
Attribution is sound because the clerk service's `run.invoker` binding admits
EXACTLY ONE named human and `verify_phase6` ASSERTS that binding is exactly
`[user:danishlynx@gmail.com]`, so widening it turns the gate red. Token decode
stays first preference; the form fallback stays emulator-gated. Record:
PROGRESS 2026-08-28; ADR-007 D2 correction note.

### C3 — `verify_phase6` authenticates with the caller's own user identity token
ADR-007 §4 originally named the `fetch_id_token` pattern; that mints
SERVICE-ACCOUNT tokens while A4 binds the clerk invoker to the named HUMAN, so
it would 403 against a correct deployment. The verifier uses
`gcloud auth print-identity-token` instead. Record: ADR-007 §4 correction
note ("recorded as a delta rather than silently deviating").

### C4 — ADR-005's false preflight claim: fix ratified (ADR-007 D12), NOT YET IMPLEMENTED
ADR-005 claims the eval preflight asserts an empty registry; it does not exist
in `evals/runner.py` (B-015 item 9; re-verified 2026-08-28 — still no hits).
ADR-007 D12 adds it and marked it droppable to Phase 7. **Owed: land the
~10-line preflight or the ADR-005 claim stays false.** Interim protection is
procedural only (RUNBOOK: registry must hold zero approved cards before evals;
`demo_reset.py --confirm` after demos). (ADR-005's status line — stale
"proposed" until the freeze — was corrected 2026-08-28; see notice block
item 5.)

### C5 — Console polish: human override of the ADR-007 D10 cut
D10 took the §11 "console polish" cut up front; the human later directed a
quality pass overriding it. A pure-CSS design system landed (no JS framework —
D1's rejection reasoning holds), then the Material-inspired design system v3
and the volume-calm queue (2026-08-28 UX ruling), zero third-party
assets/trademarks. Record: PROGRESS 2026-08-27 UI note + 2026-08-28
product-loop section (human-directed).

---

## Tally

- **ARCHITECTURE.md deviations: 31** — Δ1–Δ23 plus eight unnumbered entries
  added by the 2026-08-28 verification pass (§3.1 timers, §3.2 chunk_ids,
  §3.2/§8 BigQuery tables, §5 DLQ exemption, §6.1 auth mechanism, §9.3
  letters-rubric cut, §9.4/§13 CI cadence, Appendix B IAM artifacts). Every
  entry carries a ratification record except the three flagged
  RATIFICATION-ABSENT in the notice block (BigQuery tables, Appendix B,
  §3.1 timers); Δ7's inbox half remains the one ratification-THIN numbered
  entry.
- **Additions absent from ARCHITECTURE.md: 1** (Δ24, ratification-thin —
  recorded human authorization + B-016, no ADR).
- **Corrections to ratified ADRs: 5** (C1–C5), of which C4 is a ratified fix
  not yet implemented.
- **Standing red gate: 1** (full-set decision accuracy 75.00% (15/20) vs
  ≥85%, B-006 OPEN — measured 2026-08-28 post-fix. The 12-case CI smoke
  subset is green at 12/12 ×3 after the freeze-eve defect fix; the 8
  held-out cases measure 3/8. A measurement, not a spec change).
- **Owed at Phase 7: 1** — the ADR-007 D12 registry preflight (C4). The
  ablation-charts export closed 2026-08-29 as three hand-authored SVGs in
  `docs/charts/` (the generator still writes none — see the §9.5 delta above).

<!-- SOURCES — load-bearing claim → file:line/section (repo-relative unless noted)

CONVENTION / HEADER
- "single source of truth… via an ADR, never by silent drift": docs/ARCHITECTURE.md:5-6
- No delta-log section exists in ARCHITECTURE.md: full read of docs/ARCHITECTURE.md (431 lines, §1–§15 + appendices) — no such section present.
- B-015 "README and ARCHITECTURE delta log can cite one place": BLOCKERS.md:373-378
- "ARCHITECTURE delta log" owed at freeze: PROGRESS.md:231, PROGRESS.md:313-314

NOTICE BLOCK
- Inbox loop human-directed, no ADR: PROGRESS.md:165-197 ("Product loop + curated console (2026-08-28, human-directed…)")
- Vision authorization + per-run OK: PROGRESS.md:233-252 ("build it all as it was supposed to be and test it"), PROGRESS.md:271-273 (human per-run OK "do it")
- B-016 record: BLOCKERS.md:8-23; apis.tf "ratified 2026-08-28" comment: infra/terraform/apis.tf:15
- Ratification-absent trio: see the Δ §3.2/§8 BIGQUERY, Δ APPENDIX B, and Δ §3.1 TIMERS source lines below.
- D12 preflight not implemented: grep of evals/runner.py for registry|APPROVED|preflight → no matches (2026-08-28, this log); ADR-007 step 10 "droppable to Phase 7": docs/adr/007-console.md:602
- Red gate 75% vs ≥85%: docs/eval-report.md:9,19; B-006: BLOCKERS.md:241-263
- ADR-005 status line stale-then-corrected: docs/adr/005-resilience-architecture.md:3-7 ("RATIFIED in substance 2026-08-26… Status line updated at freeze 2026-08-28; it had never been flipped from 'proposed'"); ratification-in-substance evidence quoted there (telemetry-IAM grants as "the ADR-005 ratification ask"; Phase 3 gate "post-ADR-005 hardening")
- B-011 status line stale-then-corrected: BLOCKERS.md:799-803 ("Status: RESOLVED — the human ratified ADR-006 asks 1–5 on 2026-08-26… This line was still reading OPEN at freeze and was closed 2026-08-28")

Δ1: docs/adr/007-console.md:156-238 (D1/D2), 685-694 (§7 deltas 1); BLOCKERS.md:383-389 (B-015 #1); ratification docs/adr/007-console.md:3-8; live URLs PROGRESS.md:113-117
Δ2: docs/ARCHITECTURE.md:159-173 (§6.2 spec incl. "Model Armor… callable as an API regardless of gateway mode"); Phase 3 gate reframe ratified: PROGRESS.md:729; BACKLOG gateway-reframe row: docs/BACKLOG.md:74; GATEWAY_MODE/SAFE_MODE zero .py hits: grep **/*.py 2026-08-28 (this log); deny test audited 403: PROGRESS.md:566
Δ3: PROGRESS.md:601-603 ("in-process composition per ADR-002 item 4"); SHIP-OLD pre-committed rule + verdict: BLOCKERS.md:367-369; AgentTool experiment/revert: BLOCKERS.md:25-103 (B-009)
Δ4: docs/adr/006-model-armor-and-phase5-drills.md:241-244 (D12 note); spec: docs/ARCHITECTURE.md:74
Δ5: docs/adr/007-console.md:456 (D10 redactor row), 631 (A9); BLOCKERS.md:394-397 (B-015 #3); spec: docs/ARCHITECTURE.md:73, 370-372; per-point SDP policy (advisory 1–3, blocking 4): docs/adr/006-model-armor-and-phase5-drills.md:91-101 (D4); canary 0.0%: docs/eval-report.md:14, docs/ablations.md:39
Δ6: BLOCKERS.md:409-410 (B-015 #8); docs/adr/007-console.md:86-88, 695-697; spec: docs/ARCHITECTURE.md:80-81
Δ7: spec: docs/ARCHITECTURE.md:66 (§3.1 api row); cut: docs/adr/007-console.md:457 (upload URLs), 704-706 (§7 delta 6); inbox shipped: PROGRESS.md:170-177; receive-only fixture rule: CLAUDE.md "Data and fixture rules" ("The simulated inbox never sends real email"); runbook: docs/runbooks/video-inbox-demo.md:14-26,53-57
Δ §3.1 TIMERS: spec: docs/ARCHITECTURE.md:75 ("Cloud Tasks + Cloud Scheduler"); cloudscheduler API enabled: infra/terraform/apis.tf:9; no google_cloud_scheduler_job resource: grep infra/terraform 2026-08-28 (this log — only dead_letter/subscription/tasks resources present); Cloud Tasks time-warp proof: docs/evidence/timewarp_last_run.json + PROGRESS Phase 4 gate record
Δ §3.2 CHUNK_IDS: spec: docs/ARCHITECTURE.md:85; docs/adr/002-phase1-platform-deltas.md:3 (Status: accepted), 28-34 (item 3: RagChunk text+page_span only; one file per section; source_display_name as Citation.chunk_id key; verifier string-match)
Δ §5 DLQ EXEMPTION: spec: docs/ARCHITECTURE.md:131-132 ("every subscription has a dead-letter topic after 5 delivery attempts"); exemption text: docs/adr/006-model-armor-and-phase5-drills.md:246-255 (D13: "The two demo/replay subscriptions carry a recorded exemption from the §5 every-sub-has-a-DLQ rule (drill-lifecycle, driver-pulled, no service consumer)"); subscriptions without dead_letter_policy = timer-fired-dlq-replay + incident-raised-demo: infra/terraform/armor.tf:94-134 (timer-fired-drill HAS one at :100-101; grep infra/terraform 2026-08-28)
Δ §6.1 AUTH: spec: docs/ARCHITECTURE.md:140-142; docs/adr/003-agent-auth-and-hotadd-mechanics.md:3 (Status: accepted — ratified by the human 2026-08-20), 16-29 (decision 1: OAuth access tokens + per-resource aiplatform.reasoningEngines.query; no ID-token/audience mechanism on that leg; ID tokens remain Cloud Run pattern), 79-95 (A2A spike refuted for CLI-deployed ADK 2.7.1; consequence: proven :streamQuery transport); deny test audited 403: PROGRESS.md:566
Δ8: spec: docs/ARCHITECTURE.md:66 ("mints approval tokens"), 188-190 (§6.4); shipped: docs/adr/007-console.md:240-268 (D3), 628 (A6); BLOCKERS.md:390-393 (B-015 #2); apr-ea2cfd823116: PROGRESS.md:16
Δ9: BLOCKERS.md:217-239 (ruling 2026-08-21 + fallback + ADR-003 addendum), 150-185 (B-007 resolution + revert-not-done note); deferral: docs/adr/007-console.md:460 (D10 row); interim grant + removal condition: PROGRESS.md:567
Δ10: spec: docs/ARCHITECTURE.md:177-178; shipped setting: PROGRESS.md:368-369; ladder/negative arms: BLOCKERS.md:420-459 (B-014 final), 526-561 (ladder); "minimum confidence" explanation: docs/adr/006-model-armor-and-phase5-drills.md:103-110 (D5 amended), docs/ablations.md:77
Δ11: docs/adr/006-model-armor-and-phase5-drills.md:91-101 (D4); ratified: 401-413 (ratification record); spec: docs/ARCHITECTURE.md:177-179
Δ12: docs/adr/007-console.md:464-473 (D11), 629 (A7); Phase 5 gate scoping default: PROGRESS.md:15; A7 closed live: PROGRESS.md:213-224
Δ13: docs/adr/006-model-armor-and-phase5-drills.md:232-244 (D12), 397-399+427-429 (ask 5 accepted); BLOCKERS.md:794-797 (B-011 #3); spec: docs/ARCHITECTURE.md:228-232
Δ14: BLOCKERS.md:406-408 (B-015 #7); docs/adr/007-console.md:291 (D5 /evals row), 707-708; spec: docs/ARCHITECTURE.md:269-271
Δ §3.2/§8 BIGQUERY: spec: docs/ARCHITECTURE.md:83 (§3.2 table names), 265-268 (§8 log sink + audit.reasoning); shipped: infra/terraform/audit.tf:6-24 (one `audit` dataset; sink filter jsonPayload.audit=true; use_partitioned_tables — no named events table resource); zero hits for audit.reasoning|evals.results outside docs/ARCHITECTURE.md: grep 2026-08-28 (this log; `audit.events` appears additionally only as sink-name prose in docs/adr/007-console.md:306,313,412 — no table resource anywhere); reasoning/verifier reports inside cases/{id}: docs/ARCHITECTURE.md:98 schema as shipped per Δ6; eval artifacts: evals/results.json + evals/archive/ + docs/eval-report.md; driver-side blind spot: docs/adr/005-resilience-architecture.md:303-306 (§6.3)
Δ15: docs/adr/006-model-armor-and-phase5-drills.md:130-145 (D7), 376-379+406-408 (ask 1 accepted); BLOCKERS.md:790-793 (B-011 #2); census 15/4/3/3: PROGRESS.md:439, 812-813; spec: docs/ARCHITECTURE.md:277-285, 367
Δ16: docs/adr/006-model-armor-and-phase5-drills.md:147-175 (D8); BLOCKERS.md:777-789 (B-011 #1); tool-poisoning 3/3: PROGRESS.md:422-427; spec: docs/ARCHITECTURE.md:281-284, 302-303
Δ17: BLOCKERS.md:603-634 (root-cause: carrier measurements incl. raster no-match; A-12; substitution executed); docs/adr/006-model-armor-and-phase5-drills.md:200-216 (D10 substitution clause); PROGRESS.md:401-405 (coverage note + substitution)
Δ §9.3 LETTERS RUBRIC: spec: docs/ARCHITECTURE.md:296-299 (§9.3 "Letter quality is scored by the Vertex AI evaluation service against a small rubric (clarity, tone, accuracy) — advisory, not gating"), 377-379 (§11 cut order, rank 2); cut ratified: docs/adr/007-console.md:46-47 (cut order restated), 454 (D10 row "Letters-quality rubric | Second in the cut order"), status RATIFIED 2026-08-27: docs/adr/007-console.md:3; zero rubric code: grep **/*.py "rubric" → no files (2026-08-28, this log)
Δ18: measured table + stability + holdout + levers: PROGRESS.md:366-399; B-014 final: BLOCKERS.md:420-459; reporting rule binding: BLOCKERS.md:451-459, docs/ablations.md:60-79; gate acceptance "i accept 14/15": PROGRESS.md:15; --expect 14 default: docs/RUNBOOK.md:117-122; /Subject,/Keywords,/Author each measured: PROGRESS.md:401-404; OCR re-screen + 11/15-vs-2/15: PROGRESS.md:243-248; live containment/enrichment proofs: PROGRESS.md:275-298; spec 15/15: docs/ARCHITECTURE.md:302-303, 367-369
Δ19: docs/adr/006-model-armor-and-phase5-drills.md:186-189 (D9 narrowing); spec: docs/ARCHITECTURE.md:301-304
Δ §9.4/§13 CI CADENCE: spec: docs/ARCHITECTURE.md:301 (§9.4 "PRs run the 12-case smoke subset; `main` runs nightly full"), 394 (§13 "eval smoke on PRs, full runs nightly only"); shipped trigger: docs/adr/005-resilience-architecture.md:263 ("CI eval-smoke — fires on every push to main"); per-run-OK rule: CLAUDE.md Working Agreement, "Eval spend rule (added 2026-08-20…)"
RED GATE: docs/eval-report.md:9,19 (75.00%, FAIL line); B-006 range 65-80%: BLOCKERS.md:241-247; Phase 2 gate decision: PROGRESS.md:12; Phase 3 "stays honestly RED": PROGRESS.md:729; per-case misses: docs/eval-report.md:38-43
ABLATION CHARTS closed 2026-08-29 by hand: docs/charts/{accuracy-by-config,ablation-verifier,ablation-armor}.svg + the "Charts" table in docs/ablations.md naming each chart's source artifacts; the generator still writes none (docs/ablations.md "Charts" first sentence, matplotlib absent); DoD "ablation charts exported": CLAUDE.md Definition of done
Δ20: BLOCKERS.md:398 (B-015 #4); docs/adr/007-console.md:453 (D10 row); managed Registry API "Not enabled": docs/BACKLOG.md:81; spec: docs/ARCHITECTURE.md:370-372, 377-379
Δ21: BLOCKERS.md:399-401 (B-015 #5); docs/adr/007-console.md:301-310 (D5 rule 2, zero subscribers); spec: docs/ARCHITECTURE.md:370
Δ22: BLOCKERS.md:402-405 (B-015 #6); docs/adr/007-console.md:270-281 (D4); zero hits re-verified: grep **/*.py 2026-08-28 (this log); spec: docs/ARCHITECTURE.md:343-345, 420-421
Δ23: BLOCKERS.md:414-418 (A10 scope); docs/adr/007-console.md:368-385 (D6), 632 (A10); ratified: PROGRESS.md:21-30; exit both halves: PROGRESS.md:16, 155-163
Δ APPENDIX B: spec: docs/ARCHITECTURE.md:425-426 ("lives at docs/iam-matrix.md and is kept in sync by scripts/check_iam.py (drift fails CI)"); zero repo hits for iam-matrix|check_iam outside that sentence: grep 2026-08-28 (this log); deny test audited 403: PROGRESS.md:566; verify_phase6 role assertions: PROGRESS.md:148-151, 158; IAM evidence standard: CLAUDE.md Working Agreement ("every grant names the role, the principal, and the reason")
Δ24: zero vision/OCR hits in docs/ARCHITECTURE.md: grep 2026-08-28 (this log); intake multimodal responsibility: docs/ARCHITECTURE.md:70; pipeline + fail-closed: PROGRESS.md:240-259; live proofs (case-1216f7712d35, case-13ee94915b12, ~62s, HIGH match): PROGRESS.md:275-298; evidence-precision scope: PROGRESS.md:300-304; B-016: BLOCKERS.md:8-23; apis.tf: infra/terraform/apis.tf:15
C1: PROGRESS.md:137-141; ADR-007 D2 note: docs/adr/007-console.md:227-238
C2: PROGRESS.md:142-151; docs/adr/007-console.md:229-236
C3: docs/adr/007-console.md:544-551
C4: BLOCKERS.md:411-412 (B-015 #9); docs/adr/007-console.md:474-482 (D12), 602 (droppable); grep evals/runner.py → no matches (2026-08-28, this log); RUNBOOK procedural guard: docs/RUNBOOK.md:73-75; ADR-005 status-line correction: docs/adr/005-resilience-architecture.md:3-7
C5: PROGRESS.md:119-122 (UI note, override of D10), 185-189 (design system v3, human-directed)
TALLY: counts derived from the entries above; owed items = ABLATION CHARTS line + C4.
Live URLs: PROGRESS.md:113-117.
Evidence files referenced generally: docs/evidence/ holds 8 *_last_run.json artifacts (armor_canary, compare, demo, dlq_replay, drill_runner, injection, timewarp, tool_poisoning) — directory listing 2026-08-28.
-->
