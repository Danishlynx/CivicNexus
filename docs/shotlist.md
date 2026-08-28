# CivicNexus — video shotlist (FINAL for `docs/shotlist.md`)

Status: **DRAFT→FINAL after verdict fixes, 2026-08-28** — refuter verdict applied
(defects 1–5); not yet in the repo.
Every timing below is tagged **[M]** (measured, from repo evidence — file named in
the SOURCES block at the end) or **[E]** (estimate, honestly labeled, needs a
rehearsal measurement before this shotlist is locked).

Defensive-intent framing, stated up front per the ratified terminology rule: the
"injection" beat is a **screening drill** — a synthetic **drill fixture** from the
project's own defensive eval harness (ADR-006) exercising CivicNexus's own Model
Armor guardrails. Drill fixtures are referenced by id only (adv-001..adv-025);
their text is never quoted in this document or on camera narration.

---

## 1. The four-minute frame (fixed by CLAUDE.md Definition of Done)

| Segment | Budget | Content |
|---|---|---|
| 1. Problem | 0:30 | what municipal permit casework is, why a governed fleet |
| 2. Diagram | 0:20 | architecture diagram |
| 3. Continuous run | ≈2:00 | **ONE continuous unedited run** hitting hot-add, injection block, time-warp |
| 4. Eval dashboard | 0:30 | honest metrics incl. the RED decision-accuracy gate |
| 5. GCP console proof | 0:40 | Cloud Run / Agent Engine / Trace / Firestore / Model Armor |
| **Total** | **4:00** | ≤4:00, public YouTube, English. **Only the first 4 minutes are judged — front-load.** |

Structural note (inherited, stated honestly): the budgets sum to exactly 4:00 —
they are the CLAUDE.md numbers themselves, with **zero reserve**. Any
per-segment compression (e.g. the Shot 3 mitigation "compress Shots 1–2") is a
deviation from the DoD's stated segment budgets and belongs in the same human
ruling as §3 item 3, not made silently.

---

## 2. Timing ledger (what the repo evidence actually measured)

### Mandatory beat A — hot-add (`scripts/demo_hotadd.py`, 2026-08-26 chain)

| Step | Time | Tag |
|---|---|---|
| Warmup gate (pre-take): caseflow | 5.7s (4.3s on the Phase 4 chain; 4.8s on the attachment run) | [M] |
| Warmup gate (pre-take): treepres | 10.4s | [M] |
| BEFORE review (shows `missing_capability=True`) | **42.8s** (attempt 1, ok) | [M] |
| register `tree-preservation@1.0.0` PENDING → `agent.approved` | ≈2s (audit 05:47:54Z → 05:47:56Z) | [M] |
| AFTER review (structured `tree_preservation` finding, outcome=approve, nothing redeployed) | **502.2s ≈ 8m22s** (attempt 1, ok) | [M] |
| **On-camera floor (BEFORE + approve + AFTER)** | **≈9m07s** | [M-derived] |

The 502.2s AFTER is the **only** measured AFTER, from a warmed chain. It is the
single number that breaks the ≈2:00 slot — see §3.

### Mandatory beat B — screening drill / injection block (`make demo-injection`, A7 run 2026-08-28)

Canary timestamps from `docs/evidence/armor_canary_last_run.json`; all other
timestamps from `docs/evidence/injection_last_run.json`:

| Step | Time from run start | Tag |
|---|---|---|
| canary precondition (`armor_canary --arm positive` — runs FIRST inside `make demo-injection`, before the driver's clock starts) | ≈13–16s BEFORE driver start (canary 09:22:10.9→09:22:25.8, abutting driver start 09:22:26.2) | [M] |
| preflight (template probe, quarantine bucket, subscription, registry) | ≈16s | [M] |
| drill fixture adv-002 (pdf) minted → screened `pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE` → byte-identical quarantine → incident `inc-*` → case **QUARANTINED** | ≈33s | [M] |
| `incident.raised` consumed, byte-equal traceparent; asserts clean; **zero engine calls before the screen** | ≈40s | [M] |
| optional letters leg (`DEMO_ARGS=--with-letters`, billed): letter screened NO_MATCH at `letter_draft`, staged | ≈92s total | [M] |

Measured **make-target wall time** (what the camera sees from hitting Enter):
≈46s to QUARANTINED, ≈53s to asserts-clean — the driver-clock ≈33s/≈40s plus
the canary leg the make target runs first.

### Mandatory beat C — time-warp (`make demo-timewarp`, CLOCK_MULTIPLIER=20000, 2026-08-27 re-proof)

All timestamps from `docs/evidence/timewarp_last_run.json`:

| Step | Time from run start | Tag |
|---|---|---|
| day-0 application screened → intake → INCOMPLETE_AWAITING_APPLICANT parked | ≈21s | [M] |
| warped 12-day timer scheduled (warp 51.8s) → fired | ≈78s | [M] |
| control probe WITHOUT memory (honest ablation — cannot complete) | ≈152s | [M] |
| 3 Memory Bank recalls → resume → verifier-PASSED cited determination → PENDING_HUMAN | **≈3m19s (199s) total** | [M] |

The control probe alone consumes ≈74s of that; the warp wait ≈52s.

### Optional beat D — email → OCR → gate loop + clerk walk

| Step | Time | Tag |
|---|---|---|
| application → "email queued" → case on the (self-updating) console | ≈10s | [M, rehearsal — measured on the --once fixture drive (PROGRESS:202); no recorded measurement of a live Gmail-IMAP send exists] |
| Full email → human gate, **with floor-plan attachment** (`video_demo_email_with_plan.eml`): attachment screened + Cloud Vision OCR-extracted → intake complete → fleet review → **verifier PASSED first pass → outcome=approve** → PENDING_HUMAN | **≈62s** (case.received 11:43:21Z → PENDING_HUMAN 11:44:23Z), caseflow warmed 4.8s | [M] |
| Full email → gate, no attachment (rehearsal 1, incl. a REAL §7.3 verifier rejection + retry, outcome request_info) | 2m00s | [M] |
| Clerk walk PENDING_HUMAN → APPROVED → ISSUED → CLOSED (browser, IAM proxy); approvals row names danishlynx@gmail.com | no duration recorded; ≈20–30s of clicks | [E] |

Evidence-precision caveat that governs shot design: **the Gmail-IMAP *attachment*
leg has never fired live** — both attachment runs used the `.eml` fixture path
(`--once`). PROGRESS:302 states the rehearsal proved the IMAP hop, but the
rehearsal record (PROGRESS:202) shows a `--once` fixture drive and PROGRESS:209's
Gmail-leg rehearsal reads as planned, not performed — the record is
contradictory. Treat the ENTIRE live Gmail-IMAP hop (attachment or not) as
unproven until its one billed rehearsal (per-run OK); if unrehearsed on
recording day, open the take with the form-feed path, which is fully proven.

---

## 3. Runtime arithmetic — the honest fit problem

- Budget for the continuous run: **≈120s**.
- Serial mandatory beats at measured timings: 547s (hot-add) + 199s (time-warp)
  + 40s (screening drill driver, no letters; ≈53s as the make target incl. the
  canary leg) ≈ **786s ≈ 13m06s**.
- Maximum-overlap floor (launch everything concurrently, fill waits with the
  other beats): bounded below by the longest single beat = hot-add ≈ **9m07s**.

**Verdict, stated plainly: at the timings the repo has actually measured, the
three mandatory beats do not fit a ≈2:00 continuous run — nor a ≤4:00 video —
in any ordering.** The dominant term is the hot-add AFTER review (502.2s [M],
one data point, warmed chain, multi-capability review). Time-warp (199s [M]) also
exceeds the 2:00 slot on its own but fits a 4:00 whole-video overlap.

Levers that exist in the repo (none assumed here; each needs a decision or a
rehearsal measurement):

1. **Re-measure AFTER at video rehearsal.** RUNBOOK already mandates recording
   rehearsal timings to pace the take. 502.2s is n=1 from 2026-08-26; if a fresh
   warm AFTER lands ≤ ~110s, Plan A below fits. If it re-measures ~500s, no plan
   fits and item 3 applies.
2. **`min_instances=1` for recording day only** — ADR-005/ADR-007's costed
   video-day lever, ASK-FIRST. Note honestly: the 502.2s run was already warmed,
   so this lever mainly de-risks cold-start, not review latency.
3. **CLAUDE.md ruling.** If AFTER stays ~500s, the "one continuous unedited run
   … (≈2:00)" DoD line cannot be satisfied as written; changing it is a
   CLAUDE.md/Working-Agreement matter → human ruling (e.g., one continuous
   unedited ~4:00 take in which segments 1/2/4/5 are window-switches during
   waits — no cuts, so still literally one unedited run).
4. **Trim time-warp's on-camera length**: the ≈74s control probe is part of the
   honest ablation; skipping it on camera would need a driver flag (code change,
   human OK). Raising CLOCK_MULTIPLIER shrinks only the ≈52s warp wait.

**Decision this draft takes (recommendation, for human ratification):** shoot
the ENTIRE 4:00 as one continuous unedited screen recording. Segments 1/2/4/5
are performed live as window switches while the long-running beats stream in
visible terminals. That keeps "one continuous unedited run" literally true,
uses every wait, and is the only structure with any chance of fitting. Its
feasibility still hangs on lever 1 (AFTER re-measure) — flagged as OPEN
QUESTION 1.

### Which beat carries which measured number

| Beat | Carries |
|---|---|
| Hot-add | 42.8s BEFORE, ≈2s approve, 502.2s AFTER (all [M]) |
| Screening drill | ≈40s driver clock to QUARANTINED+incident (+≈13–16s canary precondition first inside the make target), ≈92s with letters ([M]) |
| Time-warp | 199s end-to-end; 51.8s warp; ≈74s control probe ([M]) |
| Email loop | ≈10s to case-on-screen (--once fixture drive); ≈62s to gate with attachment; 2m00s no-attachment rehearsal ([M]) |
| Clerk walk | unmeasured ([E] ≈20–30s) — measure at rehearsal |
| Warmups (pre-take) | caseflow 4.3–5.7s, treepres 10.4s ([M]) |

### Does the email→OCR→gate loop + clerk walk fit alongside the three mandatory beats?

**Yes — comfortably, and it should be the human-facing spine of the take.** At
≈62s to the gate plus ≈25s of clerk clicks it is the FASTEST full-story beat the
project has, it produces the on-camera **approve** (the 2m00s no-attachment
rehearsal produced request_info; the attachment run approved first-pass), and it
ends in the approvals row naming the human — the governance money shot. The
things that do NOT fit are hot-add's AFTER and (inside a strict 2:00 slot)
time-warp; the email loop is not the problem.

---

## 4. Plan A — shot-by-shot script (one continuous 4:00 recording)

**Conditional on OPEN QUESTION 1 (AFTER ≤ ~110s at rehearsal). All "video t="
values are planning targets, not measurements.**

### Screen furniture (arranged before recording starts)

- **W1** browser: public reader queue — https://civicnexus-console-wrhx6s33dq-uc.a.run.app (self-updating; **never press F5 on camera**)
- **W2** browser: clerk console via the IAM proxy's localhost URL
- **W3** browser: Gmail compose (clean profile) — used ONLY if the live Gmail
  leg was rehearsed (OPEN QUESTION 2); otherwise the clerk "New application"
  form replaces it
- **W4** browser: GCP console tabs pre-opened (Cloud Run, Agent Engine, Trace Explorer, Firestore `approvals/`, Model Armor template) — Google's own console; still open in the clean profile
- **T1** terminal: inbox watcher (already running, visible)
- **T2** terminal: hot-add driver
- **T3** terminal: time-warp driver
- **T4** terminal: screening-drill driver

### Shot 1 — Problem (video 0:00–0:30)

On screen: W1, the live public queue.
Narration cue: "Municipal permit casework: statutes, evidence, and decisions
that must be citable and human-accountable. CivicNexus is a governed agent
fleet that drafts the determination — and a named human signs it."

### Shot 2 — Diagram (video 0:30–0:50)

On screen: architecture diagram (OPEN QUESTION 4 — the README diagram is a DoD
item not yet built; the shot needs an artifact to point at).
Narration cue: name the trust boundary: intake screening (Model Armor +
Cloud Vision OCR), the fleet on Agent Engine, verifier, registry governance,
the human gate.

### Shot 3 — Continuous-run cluster (video 0:50–2:50 target)

**t0 = video 0:50 — staggered launch, ~15s:**

- **T3**: `make demo-timewarp` (env: `PROJECT_ID=civicnexus-hack26`,
  `CLOCK_MULTIPLIER=20000` — 12 days in ≈52s)
- **T2**: `uv run python scripts/demo_hotadd.py --skip-deploy --approver danishlynx@gmail.com`
  (env: `PROJECT_ID=civicnexus-hack26`, `REGISTRY_MODE=firestore`; RUNBOOK:
  **never** `make demo-hotadd` — it lacks `--skip-deploy`)
- **W3 or form**: feed the prepared application (subject starting "Permit
  application"). A Gmail send goes in the take ONLY if the live Gmail-IMAP leg
  was rehearsed (OPEN QUESTION 2 — the record on even the plain hop is
  contradictory, see §2's caveat); the attachment variant additionally requires
  the attachment rehearsal. If unrehearsed: use the clerk console's "New
  application" form — the SAME queue, fully proven path.

Narration: "Three things are now happening at once, live."

**t0+10s** — W1: the application's case appears by itself (RECEIVED → TRIAGED).
Narration: "An application became a case in ten seconds. No keypress — the
console updates itself." (Say "a real email" ONLY if the live Gmail leg was
rehearsed and used — the ≈10s on record was measured on the `--once` fixture
drive, per §2.)

**t0+45s** — T2: BEFORE reply lands: `missing_capability=True` (the fleet knows
it cannot review tree preservation). On camera: the driver registers
`tree-preservation@1.0.0` → PENDING → **approved by danishlynx@gmail.com**
(≈2s) → AFTER launches. Narration: "A new specialist is registered and
human-approved mid-run. No redeploy. The coordinator will route to it."

**t0+50s → t0+105s** — **T4**: `make demo-injection` (defensive screening drill;
the canary precondition runs first and occupies ≈13–16s before the driver's
clock starts — if 14/15 appears on screen the narration MUST carry its
packaging, see Shot 4). Drill fixture **adv-002** (referenced by
id; a synthetic adversarial PDF fixture from our own drill corpus) is
byte-screened → `pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE` → quarantined
byte-identical to GCS → incident raised → case **QUARANTINED**, **zero engine
calls before the screen**. W1 incidents view: metadata only, no object link.
Narration: "This is our own screening drill: a hostile document never reaches a
model. Quarantine, incident, one trace id across every audit event."

**t0+75s onward** — W1: the application case hits **PENDING_HUMAN** (≈62s [M])
with the determination card: §17.44.100 citations, verifier PASSED first pass,
outcome **approve**; case record shows
`docs=['floor_plan.png sha256:… screened+extracted']` (attachment variant).
**W2 clerk**: Approve → Issue permit → Close. Show the `approvals/` row naming
danishlynx@gmail.com. Narration: "The fleet drafted it; a named human approved,
issued and closed it — and the approval row is the audit artifact."

**t0+199s (video ≈4:09 at measured — see §3)** — T3: time-warp resume: timer
fired after the warped 12 days, control probe WITHOUT memory could not complete,
3 Memory Bank recalls, verifier-PASSED cited determination → PENDING_HUMAN.
Narration: "Twelve simulated days later the case resumes — the determination
depends on facts that exist only in Memory Bank."
**Timing note [honest]:** at measured 199s this lands *after* the 2:00 slot and,
launched at 0:50, at ≈4:09 — 9s past the video end. Mitigations: launch T3
first in the cluster, compress Shots 1–2 by ~15s (NOTE: that itself deviates
from the DoD's stated 0:30/0:20 segment budgets — a CLAUDE.md-wording tension
of its own; fold it into the same §3-item-3 human ruling, don't do it
silently), or the CLOCK_MULTIPLIER / control-probe levers (§3 item 4).
Rehearsal decides; do not fake it.

**Hot-add AFTER completion** — lands t0+547s ≈ video 9:57 at measured timing:
**outside any ≤4:00 video.** This is OPEN QUESTION 1; Plan A is only shootable
if rehearsal re-measures AFTER ≤ ~110s. Fallback below.

### Shot 4 — Eval dashboard (video 2:50–3:20)

On screen: W1 → `/evals` (the deployed page renders `docs/eval-report.md`
unedited, whatever its gate status) then the ablation tables.

Narration cues — every number packaged, none bare:

- **The gate story, stated plainly (this is the strongest honesty beat —
  do not rush it):** "This accuracy gate was **red for most of the build** —
  65 to 80 percent across five full runs — and we shipped it red on this
  public page rather than lower the threshold. The day before freeze, our
  eval instrumentation found the real defect: a stale one-permit-type
  enumeration in intake that made the verifier's legality check fail
  everything and corrupt retries. We fixed it and measured **twelve out of
  twelve, twice consecutively** — groundedness 100%, citation recall 100%,
  canary leaks zero. The red history is archived in the repo, next to the
  fix." (Scope if asked: 12-case smoke subset ×2; full 20-case set not yet
  re-measured post-fix.)
- **Screening-drill number, with its full B-014 packaging (binding rule — never
  the number alone):** "Fourteen of fifteen drill fixtures blocked, at
  `pi_and_jailbreak` **ENABLED, LOW_AND_ABOVE** — stable across three
  consecutive runs. Two levers got us here and we report them separately:
  sensitivity, loosened in measured steps only because the negative arm stayed
  clean (12 real-content controls, 0 false positives at every setting), and
  fixture strength, rewritten to what a sensitivity ladder measured. The
  progression: 0/15 at HIGH → 2/15 at MEDIUM_AND_ABOVE → 8/15 at the same
  setting after fixture strengthening → **14/15 at LOW_AND_ABOVE** (levels are
  minimums — LOW_AND_ABOVE is the most sensitive). The one holdout, adv-001, is
  characterised boundary behaviour at a 46% dilution ratio between two passing
  siblings — we deliberately did not tune it away."
- **Coverage statement — CURRENT wording (do not use stale prose):** "PDF
  byte-screening does not read text inside embedded raster images (A-12). As of
  Aug 28, intake attachments — PNG, JPEG, PDF — are transcribed by
  deterministic Cloud Vision OCR and the extracted text is re-screened as plain
  text, the screen our measurements found most sensitive; a live drill fixture
  with hostile text present as pixels only was OCR-read, matched at HIGH, and
  quarantined with zero engine calls. An attachment OCR cannot read fails
  closed to quarantine."
- **Ablations:** "Verifier off: groundedness drops 100→91.7%, citation
  precision 91.7→87.5%; the retry loop cost 2.5× tokens and corrected 0 of 7 —
  its measured value is citation fidelity, not decision correction. Armor off,
  text carriers only — 6 PDF fixtures excluded by construction: with screening
  on, 9 of 9 blocked before any model; with screening off, 7 of the 8 scoreable
  steered the fleet to approve. Indicator, not proof of obedience — there is no
  no-injection control arm."

### Shot 5 — GCP console proof (video 3:20–4:00)

On screen, W4 tabs in order (≈8s each): Cloud Run (both console services +
registry, scale-to-zero), Agent Engine (`civicnexus-caseflow`), Trace Explorer
(open the drill run's trace via its traceparent — one trace id across screen →
quarantine → incident), Firestore `approvals/` row naming danishlynx@gmail.com,
Model Armor template `civicnexus-armor`. If the time-warp resume or hot-add
AFTER is still streaming, keep T3/T2 visible in a corner and switch to them the
moment they land.

---

## 5. Fallback per beat (decided BEFORE recording, per B-003 network history)

| Beat | Fallback |
|---|---|
| Email loop | **Form feed:** the clerk console's "New application" form feeds the SAME inbox queue — paste the email body; the watcher picks it up on the next 5s poll. Loop continues identically minus the Gmail hop. Per §2's caveat this is the DEFAULT, not the fallback, until the Gmail leg is rehearsed. |
| Hot-add | Bounded-retry plan (B-006 measurement note); on FAIL read `.deploy/demo_last_run.json` FIRST (raw replies + timings persisted per attempt). If unrecoverable in-take: the recorded evidence chain (`docs/evidence/demo_last_run.json` + audit timestamps) is the honest exhibit — say so on camera rather than splicing. |
| Screening drill | 14/15 is stable across three consecutive runs with the same single holdout, and adv-002 is not the holdout — a re-run is safe. Evidence fallback: `docs/evidence/injection_last_run.json` + the quarantine object + incident in the console. |
| Time-warp | Pinned evidence case `case-5ea037e64ef8` already sits in the console with its full trail + `docs/evidence/timewarp_last_run.json`; show it and say it is the recorded re-proof. |
| Clerk walk | Two prior walks exist as Firestore evidence (`approvals/apr-79b91f861652`, `approvals/apr-ea2cfd823116`); show the row. |
| Whole-take network flake | Stop, fix, re-record the whole take — never edit. B-003 says this machine's network flakes are real; schedule slack for 2–3 full takes. |

---

## 6. Pre-flight checklist (run down IN ORDER on recording day)

1. **Branding (binding — rules disqualify):** clean browser profile, empty
   desktop, no third-party logos/trademarks anywhere — tabs, icons, wallpaper,
   taskbar.
2. **Quota-quiet window reserved:** no eval runs or CI pushes within ±30 min;
   push only `[skip ci]` during the window. Every billed leg of the take
   (hot-add, time-warp, email review, letters) has the human's per-run OK.
3. **Pinned evidence cases UNTOUCHED:** `case-5ea037e64ef8` (time-warp) and
   `case-c50219ca5166` (live demo case, ADR-007). Rehearsal residue may be
   closed or left; these two, never.
4. **Registry shows ZERO approved cards before the hot-add beat:**
   `uv run python scripts/demo_reset.py --confirm` (deletes exactly the
   `tree-preservation@1.0.0` fixture card, guarded). **Run it again after** the
   take so the eval baseline's tool surface stays clean.
5. **Warmups (MANDATORY — cold engines killed 2 prior attempts):**
   `uv run python scripts/warmup.py --engines caseflow,treepres` → must PASS
   (expect caseflow ≈4–6s, treepres ≈10s).
6. **Proxy started (before recording, leave running):**
   `gcloud run services proxy civicnexus-console-clerk --region us-central1 --project civicnexus-hack26`
   → open its localhost URL in W2.
7. **Watcher started (visible in T1):**
   `$env:PROJECT_ID='civicnexus-hack26'; $env:INBOX_EMAIL='<gmail>'; $env:INBOX_APP_PASSWORD='<typed, never saved>'`
   `uv run python scripts/inbox_watcher.py --consume --watch-gmail --i-accept-billing`
   (spend bounded by `--max-cases`, default 3; crash recovery requeues).
8. **Do NOT press F5 on camera** — queue and case pages update themselves.
9. **Secrets:** the app password is typed into the terminal only; confirm no
   env dump or history widget is on screen.
10. Timers/stopwatch off-screen; `.deploy/` evidence files verified non-zero
    after any abnormal exit (B-012 class).

---

## 7. Open questions (block the shotlist lock; owner = human unless noted)

1. **Hot-add AFTER duration.** Sole measurement is 502.2s — incompatible with
   any ≤4:00 video. Re-measure at rehearsal; if it stays ~500s, a CLAUDE.md
   ruling is needed on the "one continuous unedited run (≈2:00)" wording
   (ask-first — this draft does not change it). Related ASK-FIRST lever:
   `min_instances=1` for recording day (costed, ADR-005/ADR-007).
2. **Gmail-IMAP leg (plain AND attachment).** Resolve the PROGRESS:202-vs-302
   contradiction and rehearse the plain Gmail leg, not only the attachment
   variant: the attachment leg has never fired live, and the plain hop's only
   recorded rehearsal (PROGRESS:202) was a `--once` fixture drive while
   PROGRESS:209's Gmail-leg rehearsal reads as planned, not performed. One
   billed rehearsal through real Gmail (per-run OK) before either variant goes
   on camera — otherwise ship the form-feed path (fully proven) or the
   strengthened no-attachment fixture drive, and show the attachment case
   `case-13ee94915b12` as recorded evidence.
3. **Concurrency untested:** Plan A runs watcher + hot-add + time-warp +
   screening drill against the same project quota simultaneously; 429s killed a
   prior demo attempt. The full-cluster choreography needs one rehearsal
   exactly as scripted.
4. **Architecture diagram does not exist yet** (README DoD item). Shot 2 needs
   it.
5. **Stale coverage prose in `docs/ablations.md`** ("image-OCR injection is
   undetectable by construction") predates the Cloud Vision attachment
   pipeline. If `/evals` or the ablation tables appear on camera, either the
   doc gets the A-12/OCR-current update at freeze or the narration must carry
   the current statement (Shot 4 wording above). Same check for the README.
6. **Time-warp on-camera length** (199s): accept landing in Shot 5, or approve
   a control-probe skip flag / higher CLOCK_MULTIPLIER for the take (driver
   change = human OK).
7. **Clerk-walk duration unmeasured** — stopwatch it at rehearsal.
8. **Letters leg in-take?** `--with-letters` adds ≈52s and one billed engine
   call; screening point 3 is already live-proven. Default: leave it OUT of the
   take, mention in narration.

---

<!--
SOURCES — load-bearing claims mapped to repo evidence (file:line as read 2026-08-28)

FRAME / RULES
- 4:00 structure (0:30/0:20/~2:00/0:30/0:40), one continuous unedited run, public YouTube:
  CLAUDE.md "Definition of done" checklist (video bullet).
- Only first 4 minutes judged; public not unlisted; no third-party branding (disqualifying);
  hosted URL live through Oct 1 (judging ends Oct 1, 11:45 PM PT): docs/BACKLOG.md:20-33.
- "Must function consistently as depicted in the video" compliance clause: docs/BACKLOG.md:15-17.
- Zero-reserve note in §1: arithmetic on the CLAUDE.md budgets themselves (0:30+0:20+2:00+0:30+0:40=4:00);
  no additional source.
- Defense-framed terminology + reference fixtures by id, never quote fixture text:
  docs/RUNBOOK.md:7-39 (session framing + model routing); memory rule "Defense-framed terminology".
- B-014 binding reporting rule (never quote the number bare; setting + progression + levers +
  holdout + coverage): BLOCKERS.md:457-459 and 594-597; docs/ablations.md:62.

LIVE URLS
- Public reader + clerk URLs: PROGRESS.md:113-117.

HOT-ADD BEAT
- Chain + warmup 5.7s/10.4s + audit 05:47:54Z→05:47:56Z + PASS first attempt: PROGRESS.md:727.
- BEFORE 42.8s: docs/evidence/demo_last_run.json:7 ("seconds": 42.8).
- AFTER 502.2s: docs/evidence/demo_last_run.json:40 ("seconds": 502.2).
- Command form (--skip-deploy, never make demo-hotadd; REGISTRY_MODE=firestore;
  quota-quiet ±30min; demo_reset before; warmup mandatory; read demo_last_run.json on FAIL):
  docs/RUNBOOK.md:57-69.
- demo_reset deletes exactly tree-preservation@1.0.0, requires --confirm: scripts/demo_reset.py:1-45.
- Zero APPROVED cards before eval baseline (tool-surface): docs/RUNBOOK.md:73-75; registry
  preflight precedent BLOCKERS.md:367.

SCREENING DRILL BEAT
- Canary precondition chained FIRST inside make demo-injection: Makefile:42-43
  (`armor_canary --arm positive && demo_injection`). Canary span
  09:22:10.9→09:22:25.8 (docs/evidence/armor_canary_last_run.json started_at/finished_at)
  abutting driver started_at 09:22:26.2 (docs/evidence/injection_last_run.json) →
  ≈13–16s before driver start; make-target wall ≈46s to QUARANTINED / ≈53s
  asserts-clean = driver ≈33s/≈40s + canary leg (derived).
- Timestamps (start 09:22:26 → QUARANTINED 09:22:59 → asserts 09:23:05 → letters 09:23:58);
  adv-002 pdf; pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE; byte-identical quarantine
  (sha256 equal); inc-bc04c3c098aa; engine_calls_before_screen: 0; letters NO_MATCH at
  letter_draft, 436/200 tokens; traceparent byte-equal: docs/evidence/injection_last_run.json
  (steps array + screen/quarantine/incident/letters objects).
- A7 closed, all four §6.3 points live-measured; run-1 false-positive story: PROGRESS.md:213-224.
- make demo-injection recipe (canary precondition; letters opt-in via DEMO_ARGS): Makefile:40-43.
- 14/15 stable across three consecutive runs, same single miss: PROGRESS.md:427-428; BLOCKERS.md:437-439.
- Progression table (0/15 HIGH, 2/15 MEDIUM_AND_ABOVE, 8/15 MEDIUM_AND_ABOVE strengthened,
  14/15 LOW_AND_ABOVE; 12 controls / 0 false positives each row; confidence_level is a
  MINIMUM, so LOW_AND_ABOVE is the most sensitive setting): PROGRESS.md:420-425;
  BLOCKERS.md:425-430; docs/ablations.md:70-77.
- Two levers reported separately: PROGRESS.md:381-387.
- adv-001 holdout characterisation (46% share, siblings 45/47%, non-monotonic dilution
  MATCH 63% / NO 54,46% / MATCH 37%): PROGRESS.md:389-395; BLOCKERS.md:442-449, 648-671.
- §11 delta 15/15→14/15 honest: PROGRESS.md:396-399; BLOCKERS.md:450-455.
- verify-phase-5 --expect 14 rationale: Makefile:69-75; docs/RUNBOOK.md:116-122.

COVERAGE STATEMENT (CURRENT)
- A-12: byte-screening does not read text in embedded raster images: PROGRESS.md:401-405;
  BLOCKERS.md:617-623.
- Attachment pipeline: PNG/JPEG/PDF allowlist (3 per email, 4MB), PDFs byte-screened first,
  deterministic Cloud Vision OCR, extracted text re-screened as plain text (11/15 vs 2/15
  most-sensitive finding), provenance framing, closes A-12 at intake: PROGRESS.md:240-254.
- Fail-closed: unreadable attachment → Hostile("attachment_unreadable") → QUARANTINED:
  PROGRESS.md:255-259.
- LIVE-PROVEN: pixel-only hostile screenshot OCR-read, MATCH at HIGH, case-1216f7712d35
  QUARANTINED, inc-420ff7fd33a1, zero engine calls: PROGRESS.md:276-281.
- Stale prose flagged: docs/ablations.md:81 ("undetectable by construction") predates the pipeline.

TIME-WARP BEAT
- Timestamps 10:58:52.6 → PASS 11:02:12.1 (=199.4s); parked 10:59:14; timer scheduled 10:59:17,
  fired 11:00:10 (elapsed 53.1 / warp 51.8); control probe blocked 11:01:24.8; 3 recalls;
  outcome request_info, PENDING_HUMAN; case-5ea037e64ef8; CLOCK_MULTIPLIER 20000:
  docs/evidence/timewarp_last_run.json.
- Phase 4 chain narrative + evidence-precision scope (facts present only in Memory Bank recall);
  warmup caseflow 4.3s: PROGRESS.md:733.
- Makefile comment "20000 = 12 days in ~52s": Makefile:45-48.

EMAIL LOOP + CLERK WALK
- Rehearsal: `inbox_watcher --once` (fixture-file drive) → email → case ≈10s; full → gate 2m0s
  incl. real verifier rejection→retry→request_info; case-f319c7ccab71; budget ~2.5min + GCP
  cutaway note; the human's Gmail-leg rehearsal phrased as prospective ("doubles as the
  approve confirmation"): PROGRESS.md:199-211 (drive at :202; prospective Gmail leg at :209).
- IMAP-hop provenance CONTRADICTORY: PROGRESS.md:300-304 asserts "the rehearsal proved the
  IMAP hop itself", but PROGRESS.md:202 records a --once fixture drive and :209 reads as
  planned — no docs/evidence/*.json records a live IMAP firing. Treated as unproven in §2
  and OPEN QUESTION 2.
- Attachment run: warmed 4.8s; verifier PASSED first pass; outcome approve; ~62s
  (11:43:21Z → 11:44:23Z); case-13ee94915b12; docs=[floor_plan.png sha256 … screened+extracted]:
  PROGRESS.md:282-291.
- Watcher command + spend bound (--max-cases default 3) + crash recovery + proxy command +
  no-F5 + Gmail take steps + form-feed fallback + pinned cases rule:
  docs/runbooks/video-inbox-demo.md:14-63.
- Self-updating pages (poll /api/cases, reload on change, no keypress): PROGRESS.md:179-183.
- Human clerk walk case-f319c7ccab71 → CLOSED; approvals/apr-ea2cfd823116 naming
  danishlynx@gmail.com / issue / ISSUED at 09:27:51Z: PROGRESS.md:16.
- verify-phase-6 walk approvals/apr-79b91f861652; clerk invoker binding EXACTLY
  [user:danishlynx@gmail.com]; anonymous clerk 403: PROGRESS.md:155-163.
- Pinned video-evidence case case-c50219ca5166: docs/runbooks/video-inbox-demo.md:62-63;
  docs/adr/007-console.md:572, 656; enforced in scripts/verify_phase6.py:51 (NEVER_TOUCH).

EVAL DASHBOARD BEAT
- Headline (run 4, 2026-08-28): accuracy 100.00% GATES PASS; citation P/R 95.83/100;
  groundedness 100%; verifier first-pass 91.67%; canary 0; p50/p95 56s/68s;
  tokens 257,315: docs/eval-report.md:5-19 (regenerated from run 4).
- Red era: B-006, 65–80% across five runs, thresholds never lowered: BLOCKERS.md B-006.
- Fix + both 12/12 runs + archived history: PROGRESS.md "Accuracy levers"; evals/archive/.
- /evals renders report unedited whatever the gate status: PROGRESS.md:51.
- Verifier ablation (acc 0.0pp; groundedness +8.3pp; precision +4.2pp; caught 7 / corrected 0;
  tokens 655,564 vs 258,703 = +396,861 ≈2.5x): docs/ablations.md:26-40; PROGRESS.md:458-476.
- Verifier value = citation fidelity not decision correction; 0.0pp NOT evidence of no help
  (sample too small): PROGRESS.md:480-498.
- Armor ablation: 9 text carriers / 6 PDF excluded; 9/9 blocked at screen; 7 of 8 scoreable
  steered to approve; 1 unscoreable (adv-013, 503); indicator-not-proof, no no-injection control:
  docs/ablations.md:42-58; PROGRESS.md:509-542.

GCP PROOF BEAT
- Cloud Run/Agent Engine/Trace footage "REQUIRED by the rules": docs/runbooks/video-inbox-demo.md:45-47.
- Engine instance civicnexus-caseflow …/reasoningEngines/2118760555991793664: PROGRESS.md:601-603.
- Model Armor template civicnexus-armor: PROGRESS.md:325-327; injection_last_run.json preflight.
- Scale-to-zero services through Oct 1: PROGRESS.md:21-30 (ADR-007 ratification).

FALLBACKS / RISK
- B-003 flaky network history: BLOCKERS.md:315-329.
- Bounded-retry demo plan: BLOCKERS.md:369.
- B-012 verify .deploy evidence after abnormal exits: BLOCKERS.md:770-775.
- 429 killed attempt 5: BLOCKERS.md:371.
- min_instances=1 video-day lever (ASK-FIRST, costed): docs/RUNBOOK.md:130-132;
  docs/adr/007-console.md:636-641.
- Per-run spend OK for every billed run: CLAUDE.md Working Agreement (eval spend rule);
  docs/RUNBOOK.md:78.
- Secrets never printed/committed; app password typed only: CLAUDE.md prime directive 3;
  docs/runbooks/video-inbox-demo.md:8-9.

HONEST GAPS / ESTIMATES (not sourced because not measured)
- Clerk-walk click duration ≈20–30s: ESTIMATE, no repo measurement exists.
- All "video t=" values in Plan A: planning targets derived from the measured ledger, not measurements.
- Feasibility of Plan A: CONDITIONAL on an unrun rehearsal re-measurement of hot-add AFTER.
- Live Gmail-IMAP hop (plain or attachment): UNPROVEN pending its billed rehearsal (defect-1 fix,
  refuter verdict 2026-08-28).
-->
