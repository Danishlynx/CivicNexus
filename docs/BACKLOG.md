# BACKLOG — deferred items, timed reminders, bonus-point plan

Human-directed (2026-08-21): "remind me 4,5 later; for point 2 add Gemma if
there is any place worth adding; write up additional stuff we can do later."
This file is that write-up. Items leave this file only by being done or by
the human striking them.

## Rules re-read catches (2026-08-26, full-text sweep)

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

| When | Remind |
|---|---|
| **~Oct 8 (winners announced)** | Watch the Devpost-account email DAILY in early October: winner verification has a 2-DAY response window; missing it forfeits the prize. |
| **Video recording day** (Phase 7, ~Aug 29-30) | No third-party logos/trademarks/branding visible anywhere in the video — browser tabs, desktop icons, wallpaper, taskbar. Rules disqualify third-party branding. Record in a clean browser profile + empty desktop. |
| **Submission day** (Aug 30) | The hosted project URL submitted on Devpost must stay live and testable through the whole Judging Period (ends **Oct 1, 11:45 PM PT**). `make teardown` stays forbidden until then (guard already enforces CONFIRM_TEARDOWN). Scale-to-zero keeps idle cost ≈ 0. |
| **Submission day** (Aug 30) | Devpost deadline in the human's timezone: **Sep 1, 5:30 AM IST** (= Aug 31 5 PM PT). Internal plan submits Aug 30 — do not spend the buffer. |

## Gemma integration (human-sanctioned 2026-08-21, "add if worth adding")

Judging Stage 3: +0.2 bonus per additional Google AI model (Gemma, Veo,
Lyria), max +0.6. Scores run 1-6, so this is material.

**Recommended spot (strong fit, no production-path change):** Phase 5
injection drills — use **Gemma (serverless, Model Garden)** as the
*red-team generator* that authors adversarial injection/poisoning variants
for the Model Armor drill corpus. Rationale: attacker-model ≠
defender-model is a defensible security-engineering choice, it lives in the
eval/drill harness (not the governed runtime, so no new attack surface or
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

- Blog/content piece (+0.2): must be public, must include the line
  "created for the purposes of entering this hackathon".
- Social post (+0.2): X/LinkedIn/Instagram/Facebook with
  #AllThingsAgenticHackathon.
- Extra Google models (+0.2 each, max +0.6): Gemma plan above covers one.

## Deferred decisions awaiting their moment

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

## Credits update (2026-08-21 night): $150 hackathon credit reported in the main account (VERIFY on billing page before relying on it). Second personal GCP account with $300 trial exists - reserve it ONLY for the Phase 7 clean-project spin-up verification (a submission requirement); flag: Google's free-trial ToS is one-per-customer, human decides. Tuesday with credits: (1) revert-hybrid, (2) 2-3 variance runs of the gate (baseline was n=1 - affordable now), (3) Pro-at-decision ablation, (4) Phase 4 start. Cost guard + per-run OKs stay.
