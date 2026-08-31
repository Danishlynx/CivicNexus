# BACKLOG — deferred items, timed reminders, bonus-point plan

Human-directed (2026-08-21): "remind me 4,5 later; for point 2 add Gemma if
there is any place worth adding; write up additional stuff we can do later."
This file is that write-up. Items leave this file only by being done or by
the human striking them.

---

## Still open after submission (state as of 2026-09-01)

Submission is done. Everything below this section has either fired, been
executed, or been overtaken by the 2026-08-29 freeze; it stays in place as the
record of what was decided and when. A fresh agent needs only the three items
here.

**1. Judging window: the hosted URLs stay live until 2026-10-01, 11:45 PM PT.**

- Public reader console (no login): https://civicnexus-console-wrhx6s33dq-uc.a.run.app
- Clerk console (IAM gated): https://civicnexus-console-clerk-wrhx6s33dq-uc.a.run.app
- Both Cloud Run services run at `min-instances=0`, so idle cost stays near $0.
  Console image v0.1.6 is pinned in `infra/terraform/console_service.tf` and
  serves the honest 20-case report.
- `make teardown` is FORBIDDEN until judging closes. The `CONFIRM_TEARDOWN`
  guard stays in place; do not weaken it.
- Do not redeploy the caseflow engine or the console during the window. The
  deployed surfaces are the ones the published video depicts, and the contest
  rule "must function consistently as depicted in the video" makes that a
  compliance matter, not a preference.

**2. ~Oct 8: winner-verification email. This is the only remaining timed
reminder.** Watch the Devpost-account inbox DAILY through early October.
Verification carries a 2-DAY response window, and missing it forfeits the
prize.

**3. Post-submission engineering backlog (frozen).** Nothing here is to be
touched before judging closes unless the human explicitly reopens engineering.
It is listed so the work is not lost, not as an invitation to start it.

- **B-006, decision accuracy ships red:** full set 15/20 = 75% against the
  §9.4 >=85% gate; `docs/eval-report.md` names every miss. If work resumes this
  is item one, and the fix is the system, never the threshold.
- **`feature/code-decides` parked with ADR-008:** measured live 11/20 (20/20
  offline), reverted the same hour. Measured, not shipped.
- **Pro at the decision step:** measured 15/20, net zero. The
  `ZONING_MODEL_ID` override stays built and deployable but is not baked into
  the shipped engine. Measured, not shipped.
- **Console scale limits** (already disclosed in the README failure-modes
  section, so this is future work, not a hidden gap): the queue and
  `/api/cases` read the full collection with no pagination or index, which is
  fine at demo scale and times out near 10k cases. The fix is indexed limit
  queries, cursor pagination, and a summary projection for the poller; about a
  day, non-architectural. Review throughput is one serial watcher by spend
  design, and the human gate is the deliberate ceiling.
- **Post-demo hardening from the pre-flight audit:** `engine_iam`
  `getIamPolicy` `raise_for_status`; `store.register` narrow except
  (AlreadyExists only); Makefile `--skip-deploy` passthrough; treepres cosmetic
  tidies (stale docstrings, `mode="single_turn"` parity).
- **Clean-project spin-up was never re-verified end to end.** The README says
  so plainly in both its spin-up and failure-modes sections. Verifying it needs
  a second project and billed builds, so it is post-judging work.
- **Managed Agent Registry API still reads "Not enabled"**, and the B-007 probe
  of the registry `run.app` URLs was never revisited (revert `REGISTRY_MODE` to
  `http` only if Google's edge heals). Both are Terraform-only changes if ever
  taken.
- **Cost-shaped options that stay open but must NOT be exercised during
  judging:** the CI 6-case smoke trim, and the letters-engine deletion (idle
  engine, small standing cost). Deleting or trimming anything the video depicts
  before Oct 1 is off the table.

The spend regime still applies: hackathon credits were exhausted 2026-08-28, so
every billed action is personal money. Name the estimate and get an explicit OK
before running one. $0 actions proceed.

---

## Rules re-read catches (2026-08-26, full-text sweep)

**Status 2026-09-01: all five are settled. Historical, kept as the record.**
(1) judge access shipped as the public read-only reader console, with the
registry not public; (2) the "functions as depicted in the video" clause is now
a standing constraint on the judging window, carried above; (3) the Devpost
draft was created and the submission completed 2026-09-01; (4) the video is
public on YouTube at https://youtu.be/8mWPskk6QUo ; (5) the fallback was not
needed, the hosted console is live.

1. **Judge access (Phase 6 spec, MANDATORY):** private hosted projects must
   ship login credentials in testing instructions. Console must be judge-
   accessible by design: public read-only SAFE_MODE console (own service;
   registry stays non-public) or app-level demo login with creds in the
   submission. IAM-only access would fail the testing clause.
2. **"Must function consistently... as depicted in the video"** is a
   compliance clause — demo reliability (ADR-005) is required by rule, not
   just quality.
3. **Human action this week: create the Devpost DRAFT submission early**
   (category: Fortified Enterprise Fleet). Drafts editable until deadline;
   post-deadline nothing changes. Agent drafts all text on request.
4. Video: only the FIRST 4 minutes are evaluated — critical moments front-
   loaded. Must be PUBLIC on YouTube/Vimeo (not unlisted).
5. Fallback comfort: the app need NOT be live at the judging moment —
   video+repo proof suffices if hosting fights us (B-007).

## Timed reminders (surface these at the named moment, unprompted)

Only the Oct 8 row is still ahead. The other three fired and were executed on
the dates shown; they stay here as the record.

| When | Remind | Status |
|---|---|---|
| **~Oct 8 (winners announced)** | Watch the Devpost-account email DAILY in early October: winner verification has a 2-DAY response window; missing it forfeits the prize. | **LIVE, still ahead.** Carried to "Still open after submission", item 2. |
| **Video recording day** (Phase 7) | No third-party logos/trademarks/branding visible anywhere in the video, including browser tabs, desktop icons, wallpaper and taskbar. Rules disqualify third-party branding. Record in a clean browser profile with an empty desktop. | **FIRED AND EXECUTED 2026-08-31.** Recorded under the pre-flight branding sweep; video published at https://youtu.be/8mWPskk6QUo |
| **Submission day** | The hosted project URL submitted on Devpost must stay live and testable through the whole Judging Period (ends **Oct 1, 11:45 PM PT**). `make teardown` stays forbidden until then (the guard already enforces CONFIRM_TEARDOWN). Scale-to-zero keeps idle cost near 0. | **FIRED 2026-09-01, and it is now a standing rule rather than a reminder.** Carried to "Still open after submission", item 1. |
| **Submission day** | Devpost deadline in the human's timezone: **Sep 1, 5:30 AM IST** (= Aug 31, 5 PM PT). | **FIRED 2026-09-01.** Submitted against the 05:30 IST wall, category Fortified Enterprise Fleet. The Aug 30 internal target slipped by a day and the buffer was spent; recorded honestly. |

## Gemma integration (human-sanctioned 2026-08-21, "add if worth adding")

**Status 2026-08-29: SHIPPED, and the bonus is claimed. Everything below is
historical.** What shipped is the *second* option in this write-up, not the
first: Gemma 4 (`gemma-4-26b-a4b-it-maas`, Vertex managed API,
`location=global`) is the decidability judge at step 6 of the §7.3 verification
layer, hardened against its measured temp-0 nondeterminism by 2-of-2
self-agreement and byte-level quote verification. The drill-fixture-generator
spot recommended below was never taken. The text stays as the record of the
options weighed.

Judging Stage 3: +0.2 bonus per additional Google AI model (Gemma, Veo,
Lyria), max +0.6. Scores run 1-6, so this is material.

**Recommended spot (strong fit, no production-path change):** Phase 5
injection drills — use **Gemma (serverless, Model Garden)** as the
*drill-fixture generator* that authors the adversarial screening-drill
variants for the Model Armor drill corpus. Rationale: generating fixtures
with a model distinct from the defended pipeline is a defensible
security-engineering choice, it lives in the eval/drill harness (not the
governed runtime, so no new exposure or
IAM), and Phase 5 already includes building that drill corpus — Gemma is an
implementation upgrade to planned work, not scope creep.

**Optional second spot (only if time allows):** Gemma as a second-opinion
entailment judge in the §7.3 groundedness verifier for the eval report's
ablation chart (cross-model agreement on citation entailment). Adds
credibility to eval claims; still outside the production path.

**Not doing:** Veo/Lyria (no honest use in a permit-casework system —
gratuitous integrations read as point-chasing to judges); Gemma in the
runtime request path (violates "no features beyond spec").

Cost note: Gemma serverless is Flash-lite-class pricing; the drill corpus
is ~dozens of generations. Estimate before running, per the spend rules.

## Bonus content (already in CLAUDE.md Definition of Done, restated with points)

**Status 2026-09-01: all three claimed.** The blog post is published on dev.to
carrying the required "created for the purposes of entering this hackathon"
line; a LinkedIn post is published with #AllThingsAgenticHackathon; the extra
Google model is Gemma 4, per the section above. The published URLs live in the
Devpost submission, not in this file.

- Blog/content piece (+0.2): must be public, must include the line
  "created for the purposes of entering this hackathon".
- Social post (+0.2): X/LinkedIn/Instagram/Facebook with
  #AllThingsAgenticHackathon.
- Extra Google models (+0.2 each, max +0.6): Gemma plan above covers one.

## Deferred decisions awaiting their moment

**Status 2026-09-01: HISTORICAL. Every row's named moment (the Phase 3, 5, 6
and 7 gates, the Aug 24 credit check, freeze day) has passed, phases 0 through
6 are complete, and the tree is frozen at `main` = 985812e.** The rows below
are kept as the record of what was deferred and when. Rows still genuinely live
after submission were lifted into "Still open after submission" at the top of
this file; for the rest, the phase records in `PROGRESS.md` are authoritative
for how each one was actually taken.

| Item | Waits for |
|---|---|
| Gateway-scope reframe discussion (ADR-003 consequence: gateway = policy/screening/audit while platform IAM enforces identity — a §6.1 plan deviation to ratify explicitly) | Phase 3 gate |
| Pro-at-decision-step ablation: `gemini-2.5-pro` / `gemini-3.1-pro-preview` now serve (B-006 addendum 2); costed proposal + per-run OK | Phase 5 re-measurement |
| Corpus content question: tree-preservation demo cites Ch. 17.44 (home occupations) because the corpus has no tree ordinance chapter; decide whether to add one (attribution rules apply) for a stronger video moment | Phase 3 gate |
| CI smoke red: borderline-case variance investigation | Phase 3 gate prep |
| CI 6-case trim offer (halves per-push cost) | Human option, open |
| Letters-engine deletion offer (idle engine, small standing cost) | Human option, open |
| Post-demo hardening from the pre-flight audit: engine_iam getIamPolicy raise_for_status; store.register narrow except (AlreadyExists only); Makefile --skip-deploy passthrough; treepres cosmetic tidies (stale docstrings, mode="single_turn" parity) | After demo-hotadd PASS |
| Managed Agent Registry API (console shows "Not enabled"): enable via Terraform only, at the Phase 6 managed-bind attempt | Phase 6 |
| B-007 re-probe of registry run.app URLs (revert REGISTRY_MODE to http when Google's edge heals) | Before Phase 6 |
| Hackathon credit: form submitted 2026-08-21, expected ~Aug 24; verify on billing page, then revisit Phase 5 eval budget | ~Mon Aug 24 |
| Clean-project spin-up: image vars default to THIS project's registry (A8 safety); fresh project must build both images then override per terraform.tfvars.example — put in README spin-up steps | Phase 7 |
| One intentional CI push before freeze (first-ever run of emulator tests under widened testpaths; rides billed eval-smoke, needs spend OK) | Freeze day |
| README failure-modes MUST state the scale limits honestly: console queue + /api/cases read the full collection (no pagination/index — fine at demo scale, times out at ~10k cases; fix = indexed limit queries + cursor pagination + summary projection for the poller, ~1 day, non-architectural); review throughput is one serial watcher by spend design (parallel Cloud Tasks consumers are the scale shape); the human gate is the deliberate throughput ceiling | README writing (Phase 6/7) |

## Credits update (2026-08-21 night): HISTORICAL

Superseded 2026-08-28, when the credits were exhausted. From that date every
billed action is personal money and needs a named estimate plus an explicit OK.
The Tuesday list below was worked through across Phases 3 to 5; `PROGRESS.md`
is authoritative for what actually ran and what it measured.

Original entry: $150 hackathon credit reported in the main account (VERIFY on billing page before relying on it). Second personal GCP account with $300 trial exists - reserve it ONLY for the Phase 7 clean-project spin-up verification (a submission requirement); flag: Google's free-trial ToS is one-per-customer, human decides. Tuesday with credits: (1) revert-hybrid, (2) 2-3 variance runs of the gate (baseline was n=1 - affordable now), (3) Pro-at-decision ablation, (4) Phase 4 start. Cost guard + per-run OKs stay.
