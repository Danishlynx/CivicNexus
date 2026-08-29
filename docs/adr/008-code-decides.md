# ADR-008: The model extracts facts; code decides the outcome

- **Status:** PROPOSED, then MEASURED and PARKED — not ratified, not the
  default. *(Status line corrected 2026-08-29 when this ADR was copied onto
  `main`: it originally read "not measured live", which stopped being true
  the same day — the architecture was measured live at 11/20 and reverted per
  the pinned ≤16 rule. See "Measured result" at the end of this file.
  Ratification remains the human's, and nothing here is ratified.)*
- **Date:** 2026-08-29
- **Deciders:** pending the human's review. Nothing here changes behaviour
  unless `DECISION_MODE=code` is set, and the default is `model`.
- **Relates to:** B-006 (§9.4 accuracy gate red), ADR-004 (LLM proposes, code
  enforces), ARCHITECTURE §7.3 (verifier), §9.4 (gates).

## 1. Context — what was measured

The §9.4 decision-accuracy gate is 0.85. The fleet does not reach it, and the
record says precisely why.

**Run-to-run variance at temperature 0.** Five full 20-case PermitBench runs on
2026-08-19 scored **80% → 70% → 80% → 65% → 70%**, and the 80/70 pair was the
*same configuration*: recorded in PROGRESS as "(same config: run variance)".
The 12-case smoke subset shows the same signature — 10/12 then 9/12 on
identical wiring, twice on different dates. Both the zoning agent and the
verifier's judges already run at `temperature=0.0`; `zoning.py` even carries the
comment "A legal reviewer must be deterministic: identical facts, identical
ruling." It is not.

**The variance is in the decision, not the law.** Per-case forensics across the
three full runs with case-level data: permanent misses 010 and 020; churners
008 (OK, OK, MISS), 013 (MISS, OK, MISS), 014 (OK, MISS, MISS). And the line
that decides this ADR: **"4 of 5 misses had CORRECT citations: the failure is
decisions, not law or retrieval."** Groundedness held at 90–100% and citation
P/R at 0.90–0.95 throughout.

**A stronger model does not fix it.** The 2026-08-28 ablation ran
`ZONING_MODEL_ID=gemini-2.5-pro` at the decision step against the Flash
baseline, same 20 cases, same day. Both scored **15/20** — with *different*
misses. Pro fixed 008 and 010 and gave both back by regressing 009 and failing
017 on output-schema validation. The recorded conclusion: **"Model tier is not
the constraint for these cases"** — measured, not assumed.

**LLM-on-LLM correction bought nothing.** The verifier ablation is blunter
still: "the retry loop cost 2.5x the tokens and corrected zero of the seven
findings it retried… What the verifier IS buying, measured: groundedness
first-pass 100% vs 91.7% and citation precision 91.7% vs 87.5%. **Its value in
this system is citation fidelity, not decision correction.**"

The pattern across every lever tried: the *deterministic* parts of the pipeline
carry their weight, and the generative decision step does not. The two changes
that ever moved the number were both non-model — an intake enum defect fix and
a config taxonomy entry.

The failure taxonomy the study settled on is symmetric, which is itself
diagnostic. **Over-asking** (010, 013, 020: `request_info` where stated facts
already decide) and **over-deciding** (008, 014: `deny` where a decision-critical
fact is genuinely absent) are the same defect seen from two sides: no stable
checklist of which elements a section imposes, which of them are live, and which
absences actually matter. That is not a knowledge problem. It is a bookkeeping
problem, and bookkeeping is what code is for.

## 2. Decision

Split the review step in two.

1. **The model extracts.** A new agent (`zoning_extract.py`) retrieves sections
   exactly as today and reports, per statute element, a `ProvisionFact`:
   `{provision, element, status ∈ {satisfied, violated, hedged, absent},
   stated_value, quote}`. It is told, in capitals, that it does not decide the
   application, and it is never given the outcome vocabulary — naming an
   outcome to a reader is what steers it (the 2026-08-28 golden-004 flip).

2. **Code decides.** A new workspace library, `libs/decision`, holds the
   statute as data and the decision as a pure function:
   - `facts.py` — the fact-sheet schema.
   - `rules.py` — 14 corpus sections, 82 elements, each classified
     `PROHIBITION` (silence is not a violation), `THRESHOLD` (an eligibility
     precondition or required application content, so silence *is*
     decision-critical), or `TRIGGER` (switches other elements on, and never by
     itself denies). Plus applicability: specific-controls-general, the
     §17.44.200 savings clause, and `requires` chains resolved to a fixpoint.
   - `decide.py` — composes the outcome, and cites `data/corpus/<section>.txt`
     for every controlling provision by locating the exact verbatim span.

The ordered rule is unchanged, verbatim from the zoning agent's instruction:
any unambiguous violation of an applicable provision denies; a decision-critical
element absent or hedged asks, naming it; otherwise the stated facts satisfy
every applicable requirement and the application is approved as stated.

**Where the code can compute the answer, the model's status does not vote.**
If a `stated_value` yields exactly one quantity in the element's unit, the code
recomputes the status. Zone tokens are classified against a corpus-derived
table rather than by the reader. The `_quote_confirmed` discipline of §7.3 steps
5 and 6, generalised to the decision itself.

The hedging rule is drawn mechanically, and the line is *whether a number was
stated*, not whether a hedging word appears: "about 3 feet" quantifies and is
decided on its quantity; "well before sunrise" and "two houses down the block"
do not quantify at all and therefore cannot settle a clock or footage threshold.
That is the §7.3 step-6 prompt's own rule — "an approximate or relative
statement does not settle a numeric or clock-time threshold" — moved from a
prompt a model may or may not follow into code that always does.

## 3. What this fixes, and what it does not

**Fixes: decision-layer nondeterminism.** Given the same fact sheet, the outcome,
the citations and the rationale are byte-identical every run. A test asserts it.
The composition failures the study named are structurally impossible: the
checklist cannot shrink (over-decide) or pad (over-ask), because it is a
literal in a registry rather than a recollection.

**Does not fix: extraction-layer judgment.** Three things stay with the model,
and each remains a live source of error:

- **Which sections are engaged.** Section-level applicability is still the
  reader's call — `rules.py` evaluates the sections whose facts appear on the
  sheet. If retrieval misses §17.44.103, no rule can rescue the case. (The
  co-retrieval of §17.44.100 that sank golden-008 *is* now survivable, because
  suppression is code — but the inverse omission is not.)
- **Per-element status.** "Does this sentence satisfy (F)(2)?" is a reading
  judgment. The code overrides only where a number or a zone token settles it.
- **`stated_value` scoping.** The field must carry the value for *that element*.
  A value belonging to a neighbouring element corrupts the comparison. The
  prompt says so explicitly; nothing enforces it.

So the honest claim is narrow: **this removes variance from the composition
step and leaves it in the reading step.** Whether total accuracy improves is an
empirical question this ADR does not answer.

**Also unfixed by design:** golden-013's borderline calibration and golden-020's
taxonomy gap are decided correctly by the rules offline, but only because the
fact sheets are correct. The instrument defect in golden-014 was repaired in the
dataset (B-006 addendum 3), not here.

## 4. Evidence available now — offline only

`libs/decision/tests/test_rules_golden.py` supplies, for each of the 20 golden
cases, the fact sheet a correct extraction would produce from that case's
fixture, and asserts the rules reach the expected outcome and cite the required
section. **20/20, including all five cases that ever wobbled (008, 010, 013,
014, 020) and both permanent misses.**

Three guards keep this from grading its own homework:

- Expectations load from `evals/permitbench/cases/*.yaml` — the frozen dataset —
  not retyped in the test.
- Every `quote` is asserted to be a verbatim span of that case's fixture
  document, so a fact sheet cannot smuggle in a fact the applicant never wrote.
- Every `element` key is asserted to exist in the registry, so a typo cannot
  silently delete an element from the checklist.

Additionally: every one of the 82 rule quotes is asserted to be a *unique*
verbatim span of its corpus section, and every citation the rules emit is
asserted to pass the same normalization §7.3 steps 1–2 apply — so groundedness
is 1.0 by construction on this path, not by hope.

`test_rule_nuances.py` pins each legal ruling as a *flip*: the same facts with
one thing changed produce a different, also-correct outcome. Rules that merely
memorised the answer key would fail those.

**This is not an accuracy claim.** It is the claim that the rule layer is
correct on the golden set *given correct extraction*. No live run has been made.

## 5. Implementation notes

- **Flag:** `DECISION_MODE=code|model`, default `model`. `coordinator.py`
  selects the specialist via `select_zoning_specialist()`; both agents are named
  `zoning` and fill the same slot, so the coordinator instruction is unchanged.
  `zoning.py` is untouched.
- **Checklist delivery:** deployed agent bundles cannot import workspace
  libraries (the constraint `caseflow_agent/schemas.py` already documents), so
  the driver renders `checklist_text()` and ships it in the review request.
  This costs prompt tokens — the full 82-element checklist measures **11,393
  bytes**, added to every review request including retries — and is a
  measurement variable, not a free choice. Sending only the retrieved sections'
  elements is impossible without a second round trip.
- **Failure mode:** `decide()` raises `UndecidableError` when the fact sheet
  engages no section it has rules for, or when a rule's quote anchor is no
  longer in the corpus. It never guesses; the runner records the case as an
  error, which counts against accuracy honestly.
- **Outcome legality:** a decided outcome outside the permit type's
  `allowed_outcomes` is *reported* (`outcome_allowed=False`), never rewritten.
  Steering an outcome from config is prime-directive-9 territory, and §7.3
  step 4 is the gate.
- **Per-permit-type rule functions** exist as the brief specified, but the
  finding is that the real dispatch key is the statute section, not the permit
  type: `accessory_structure` alone reaches eight of the fourteen sections, and
  §17.44.100 serves three permit types. The per-type entries today differ only
  in the label they put in the rationale.

## 6. Measurement plan — NOT YET RUN, and it costs money

Pre-committed here so the result cannot be read backwards into the rule, per the
discipline the human established for the lever-1 and Pro runs.

**Runs:** two full 20-case runs at `DECISION_MODE=code`, same configuration both
times, no between-run tuning. Compared against the archived Flash baseline
(`evals/archive/results-full-20260828.json`, 15/20) and the archived Pro
ablation (`results-pro-at-decision-20260828.json`, 15/20).

**Rule pre-commitment is left to the human.** This ADR deliberately does not
write the ship/revert thresholds — the author of a change should not also set
the bar it is judged against. Proposed for the human's decision, to be fixed
*before* the first run:

- What both-run score ships the mode as default.
- What score records it as "measured, not the constraint" and keeps `model` the
  default.
- Whether the hard guard from the above-85 push carries over: if any case whose
  expected outcome is `request_info` (004, 008, 011, 014, 017, 019) regresses,
  stop and investigate.

**Two numbers worth reading independently of the headline:**

1. **Variance.** Two runs of the same config is the direct test of the property
   this ADR claims. Identical per-case results across both runs is the result;
   the accuracy number is secondary.
2. **The split.** Every remaining miss is now attributable: `UndecidableError`
   and wrong-section engagement are retrieval; a wrong outcome on a complete
   fact sheet is extraction status; and a wrong outcome that the offline golden
   test also produces would be a rule defect. The 20/20 offline result says
   there are currently none of the third kind.

**Spend:** unestimated here. Two full runs at Flash prices were estimated at
~$2–4 (~₹180–350) for the above-85 push; the code path adds the checklist to
every review prompt and removes nothing, so it will be somewhat more. Per the
credits-exhausted regime, the estimate must be named in dollars and rupees and
explicitly approved before any run.

**Commands (do not run without that approval):**

```bash
# Offline, $0 — the evidence that exists today.
uv run pytest libs/decision -q
make test

# Live, BILLED — requires PROJECT_ID, a deployed engine, and the human's OK.
DECISION_MODE=code uv run python -m evals.runner --tag smoke   # 12-case subset
DECISION_MODE=code uv run python -m evals.runner --report      # full 20-case

# Archive each run under its arm before the next one, so neither can be
# mistaken for the baseline:
#   cp evals/results.json evals/archive/results-code-decides-run1-<date>.json
# The Flash artifact remains the baseline until a ratified rule says otherwise.
```

## 7. Rollback

Unset `DECISION_MODE` (or set it to anything but `code`). The default path is
`zoning.py` + `ReviewFinding`, unchanged; `libs/decision` is then imported by
the drivers but never invoked on the decision path. `make test` passes with the
flag absent, which is the regression evidence that the default did not move.

## 8. Consequences

**Good.** The decision becomes auditable line by line — a citizen or a judge can
read `rules.py` and see the rule that decided their permit, which a sampled
decoder cannot offer. Rule changes get diffs, review and tests. Every miss
becomes attributable to a named layer.

**Bad.** The statute now lives in two places (the corpus and the registry), and
they can drift; `decide()` fails loudly on drift rather than silently, but
someone still has to maintain 82 elements. Adding a section is now code, not
retrieval — the system generalises to new law only as fast as someone writes
rules for it. That is a real cost, and for a demo of *governed* casework it is
arguably the honest trade; for a system claiming to read arbitrary municipal
code it would not be.

**Uncertain.** Whether extraction is materially more reliable than decision.
The study's evidence is suggestive — 4 of 5 misses cited correctly, meaning the
reading was right where the composing was wrong — but nobody has measured
per-element extraction accuracy directly. If extraction wobbles as much as
decision did, this moves the problem rather than solving it, and the two-run
variance check in §6 is what would reveal that.

## Measured result (2026-08-29, appended at parking)

Live run 1 (valid, after the deploy-env fix): **11/20 (55%)** — reverted per
the pre-pinned <=16 rule. The rule layer delivered where extraction scoped
correctly (002, 008, 014, 020 all correct — including the never-passing 020
and the harmonization case 008), but extraction over-engaged inapplicable
sections and their absent elements drove 8 over-asks (citation precision
0.39, p95 267s, 1.43M tokens). Verdict: composition determinism proven
necessary but not sufficient; the frontier is extraction/applicability
scoping. Branch parked measured, not shipped. Artifacts in the main repo:
evals/archive/results-codedecides-run1-{INVALID-envgap,valid}-20260829.json.
