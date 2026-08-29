# CivicNexus — video script (read aloud, one continuous screen recording)

**Target runtime 3:56 / hard cap 4:00. Narration 531 words at 135 wpm.**
Every timing in the `[SCREEN]` blocks is sourced from `docs/shotlist.md` §2
(the measured ledger) and tagged **[M]** measured or **[E]** estimate. All
`video t=` values are planning targets, not measurements.

**Structure is ratified, not improvised.** Per the human's video-structure
ruling (PROGRESS.md, "FREEZE DECLARED — 2026-08-29"), the continuous take
carries the **live product loop** (application → OCR → gate → clerk) plus the
**screening drill**; **time-warp runs live in-take only if rehearsal timing
allows**; **hot-add is proven via its recorded evidence plus the registry UI**
in the proof segment. That is a recorded deviation from the internal
Definition-of-Done wording, taken because hot-add's measured AFTER review
(≈502s) cannot fit a 4:00 video — not silent drift. This script implements
that ruling exactly.

Defensive framing (binding, per the ratified terminology rule and B-014): the
security beat is a **screening drill** using a synthetic **drill fixture** from
this project's own defensive eval harness (ADR-006). Fixtures are referenced by
id only; their text is never shown or read aloud.

---

## PREP HEADER — run down IN ORDER before the recording light goes on

Nothing below happens on camera.

1. **Branding sweep (rules disqualify third-party branding).** Clean browser
   profile, empty desktop, no third-party logos on tabs, icons, wallpaper or
   taskbar. Google's own console is fine — it's the platform being demoed.
2. **Quota-quiet window:** no eval runs or CI pushes within ±30 min. Every
   billed leg of this take has the human's per-run OK.
3. **Registry reset:** `uv run python scripts/demo_reset.py --confirm`
   (deletes exactly the `tree-preservation@1.0.0` fixture card). Run it again
   after the take so the eval baseline's tool surface stays clean.
4. **WARMUP — mandatory, cold engines killed two prior attempts:**
   `uv run python scripts/warmup.py --engines caseflow,treepres` → must PASS.
   Expect caseflow ≈4–6s, treepres ≈10.4s **[M]**.
5. **Clerk proxy (start, leave running):**
   `gcloud run services proxy civicnexus-console-clerk --region us-central1 --project civicnexus-hack26`
   → open the localhost URL it prints in **W2**.
6. **Watcher (start, leave VISIBLE in T1):**
   ```powershell
   $env:PROJECT_ID='civicnexus-hack26'
   $env:INBOX_EMAIL='<gmail address>'
   $env:INBOX_APP_PASSWORD='<typed, never saved>'
   uv run python scripts/inbox_watcher.py --consume --watch-gmail --i-accept-billing
   ```
   Spend is bounded by `--max-cases` (default 3). Confirm no env dump or
   history widget is on screen — the app password is typed only.
7. **Drill command staged, NOT run**, cursor parked at the end of the line in
   **T4**: `make demo-injection`. (No `--with-letters` — it adds ≈52s **[M]**
   and one billed engine call for a point already live-proven.)
8. **Windows arranged:** W1 public reader queue
   (https://civicnexus-console-wrhx6s33dq-uc.a.run.app) · W2 clerk via proxy ·
   W3 Gmail compose (or the clerk "New application" form — see CONTINGENCY) ·
   W4 GCP tabs pre-opened in order: Cloud Run, Vertex AI Agent Engine, Trace
   Explorer, Firestore `approvals/`, Model Armor template · T1 watcher ·
   T4 drill.
9. **NEVER PRESS F5 ON CAMERA.** Queue and case pages poll and update
   themselves.
10. **Pinned evidence cases are untouchable:** `case-5ea037e64ef8` (time-warp)
    and `case-c50219ca5166` (ADR-007 video evidence). Rehearsal residue may be
    closed; these two, never.
11. Stopwatch off-screen. After any abnormal exit, verify `.deploy/` evidence
    files are non-zero before re-taking (B-012 class).

---

## SEGMENT 1 — Problem · video 0:00–0:30 · 66 words ≈ 29s

**[SCREEN]** Open on **W1**, the live public queue at
`civicnexus-console-wrhx6s33dq-uc.a.run.app`. Scroll slowly through the case
rows once. Do not click. Let the URL bar stay visible.

**[SAY]**
> "This is CivicNexus, live. A queue of municipal permit cases — synthetic
> data, real system. Behind every row like this is a person waiting weeks,
> sometimes months, for a decision a statute already determines. The clerk
> isn't slow. The clerk is the message bus: their day is reading and routing,
> not deciding. We gave the reading to a governed fleet of agents and kept the
> deciding human."

---

## SEGMENT 2 — Value proposition · video 0:30–0:50 · 50 words ≈ 22s

**[SCREEN]** Switch to the README's **Architecture (as actually deployed)**
mermaid diagram — full-screen, checked for legibility at recording resolution
before the take. Trace with the cursor as you speak: intake + attachment
pipeline → the screening band → the fleet on Agent Engine → verifier →
registry → **the human gate**. Rest the cursor on the human gate on the last
sentence.

**[SAY]**
> "One fleet, on Google Cloud. It reads the mail, screens every attachment
> before a model sees it, retrieves the municipal code, drafts determinations
> with verbatim citations, and verifies them byte for byte. It can do all of
> that alone. What it cannot do is sign. Autonomy everywhere except the
> signature."

---

## SEGMENT 3 — Live demo · video 0:50–2:55 · 250 words ≈ 111s

**One continuous recording. Two things launch inside the first 15 seconds and
run concurrently — that is what makes this fit.** Segment 3 carries ~13s of
deliberate slack for clicks and page loads; do not fill it with extra words.

### 3a · t=0:50–1:05 — launch both

**[SCREEN]** **W3**: send the prepared application
(`data/fixtures/video_demo_email_with_plan.eml` content — subject starting
"Permit application", floor-plan image attached) to your own address. Then
**immediately** switch to **T4** and press Enter on `make demo-injection`. Let
the terminal scroll visibly.

**[SAY]**
> "I'm filing a permit application right now — a home bakery, with a floor plan
> attached. And in this terminal, our own screening drill starts against the
> same intake path. Both run live, at once."

> **[NOTE, not spoken]** If the form-feed path is in use (see CONTINGENCY),
> the first sentence becomes: *"I'm filing a permit application right now
> through the clerk's intake form — a home bakery, with a floor plan
> attached — into the same queue an email lands in."* Do **not** say "a real
> email" unless the live Gmail-IMAP leg was rehearsed and is what you just
> used: shotlist §2 records that hop as unproven, and the ≈10s figure below
> was measured on the `--once` fixture drive.

### 3b · t=1:05–1:22 — the case appears by itself

**[SCREEN]** **W1**. The new case appears on its own, RECEIVED → TRIAGED
(≈10s **[M, rehearsal, `--once` fixture drive]**). Hands off the keyboard —
the audience must see you not refreshing. Open the case; point at the
`docs=[floor_plan.png sha256:… screened+extracted]` line on the case record.

**[SAY]**
> "Ten seconds — it's a case. I didn't refresh; the console updates itself.
> That attachment never went straight to a model: byte-screened, transcribed by
> Cloud Vision — a transcription engine, so pixels can't give it instructions —
> then re-screened as text."

### 3c · t=1:22–1:45 — the drill lands (concurrent)

**[SCREEN]** Switch to **T4**. Expected make-target wall time ≈46s to
QUARANTINED, ≈53s to asserts-clean **[M]** — with Enter pressed at ≈0:52 that
lands ≈1:38 / ≈1:45. Show, in the driver output: `pi_and_jailbreak
MATCH_FOUND at LOW_AND_ABOVE` → byte-identical quarantine (sha256 equal) →
`inc-*` raised → case **QUARANTINED** → `engine_calls_before_screen: 0`.

**[SAY]**
> "And there's the drill landing. A hostile document from our own defensive
> fixture set — flagged at the screen, quarantined byte-identical, incident
> raised, case quarantined. Zero engine calls. It never reached a model, and no
> human was asked. The fleet defended itself while it was working."

### 3d · t=1:45–2:00 — fill the review wait with the verifier

**[SCREEN]** Back to **W1**, the live case, still in review. Leave T4 visible
in a corner if the layout allows.

**[SAY]**
> "Meanwhile the review is finishing. Every citation gets checked byte-exact
> against the committed corpus. And when the fleet asks for information instead
> of deciding, a second model — Gemma — has to name the fact that already
> decides it."

> **[NOTE, not spoken]** Deliberately conditional. The Gemma decidability check
> is step 6: it only engages a `request_info` finding that has cleared steps
> 1–5. In its one full-run measurement it fired **zero** times. Never narrate it
> as something happening to *this* case.

### 3e · t=2:00–2:28 — determination lands, then the clerk walk

**[SCREEN]** The determination card appears on its own (measured ≈62s from
`case.received` to PENDING_HUMAN on the attachment run **[M]**, so ≈1:57 at a
0:55 receive). Point at the verbatim **§17.44.100** citation and the
verifier **PASSED** tag, outcome **approve**. Switch to **W2 (clerk)**:
**Approve → Issue permit → Close** (≈20–30s of clicks **[E]**, unmeasured).
Then show the `approvals/` row naming the human operator.

**[SAY]**
> "There it is. Section 17.44.100, quoted verbatim. Verifier: passed. Now the
> only part a machine can't do. I'm the named human. Approve. Issue the permit.
> Close. And that wrote a write-once approvals row with my identity in it — the
> permit could not exist without it."

> **[NOTE, not spoken]** **Read the citation and the verifier tag off the
> screen — do not pre-commit to them.** §17.44.100 and "verifier passed" are
> what the measured attachment run produced; outcome variance is real and
> characterised (B-006: identical facts have yielded `deny` vs `request_info`
> across runs). If the live card differs, say what is actually on it. Two live
> substitutions, both true and both still strong:
> - Different section: *"There it is — section [whatever it says], quoted
>   verbatim, and the verifier checked that quote byte-for-byte."*
> - Outcome is `request_info` or the verifier report reads FAIL: *"The fleet
>   asked for more information rather than deciding — and note the verifier's
>   report travels with it, pass or fail. Either way it stops here, for me."*
>   The clerk walk still works: the case sits at PENDING_HUMAN on every path,
>   and the human decides.

### 3f · t=2:28–2:55 — close on the incident

**[SCREEN]** **W1** → the incidents view → the incident just raised by the
drill. Show that it renders **metadata only** — no object link, no bytes. Show
the single traceparent shared by screen, quarantine and incident.

**[SAY]**
> "Back to the incident. Metadata only — quarantined bytes are never served.
> One trace id links the screen, the quarantine and the incident. So: this
> system was attacked mid-run and it decided alone. Contained before any model
> saw it, and before any person saw it. That's what governed autonomy has to
> mean."

---

## SEGMENT 4 — The honesty beat · video 2:55–3:25 · 81 words ≈ 36s

**[SCREEN]** **W1 → `/evals`** (renders `docs/eval-report.md` unedited,
whatever the gate says). Land on the red **Decision accuracy 75.00% · ≥85% —
FAIL** row and hold there for the first two sentences. Scroll to **Where it
still fails** so the five named misses are on screen. Then cut to
`docs/charts/accuracy-by-config.svg` and `docs/charts/ablation-armor.svg`.

**Do not rush this. It is the strongest beat in the video.**

**[SAY]**
> "The number I'm proudest of: full-set accuracy, seventy-five percent. Red —
> below our own gate, shipped red on our public evals page, threshold never
> lowered, every miss named. Same run: groundedness one hundred percent. Our CI
> subset: twelve for twelve, three runs straight. Screening on, nine of nine
> blocked before any model; off — text carriers only — seven of the eight that
> scored steered the fleet to approve. Every run behind those numbers is
> archived in the repo. Judge us by re-running us."

---

## SEGMENT 5 — Google Cloud proof · video 3:25–4:00 · 84 words ≈ 37s

**[SCREEN]** **W4** tabs, ≈6s each, in this order — keep the `.run.app` URL
bar visible on the first one:

1. **Cloud Run** — three services (public reader, IAM-gated clerk, private
   registry), all scale-to-zero.
2. **Vertex AI Agent Engine** — the deployed instances (`civicnexus-caseflow`
   and the rest of the fleet).
3. **Trace Explorer** — open the drill run's trace by its traceparent; the
   waterfall, one trace id across screen → quarantine → incident.
4. **Firestore** — the `approvals/` collection, the row naming the human.
5. **Model Armor** — the `civicnexus-armor` template.
6. **W1 → the registry page** — the approved specialist card.

End card: repo URL + `https://civicnexus-console-wrhx6s33dq-uc.a.run.app`.

**[SAY]**
> "Google Cloud throughout. Infrastructure, all Terraform. Cloud Run: three
> services. Vertex AI Agent Engine: four agents, four least-privilege
> identities. Trace: one waterfall across the case. Firestore: the approvals
> row with my name. Model
> Armor: the template that screened. And the registry, where a new specialist
> was registered and human-approved mid-run with nothing redeployed — that run,
> and a twelve-day gap resumed from Memory Bank in a measured hundred and
> ninety-nine seconds, are recorded evidence in the repo. Repo and console, on
> screen. Go re-run us."

> **[NOTE, not spoken]** The hot-add and time-warp sentences are deliberately
> phrased as **recorded evidence**, because they are not live in this take.
> Hot-add's measured AFTER review is 502.2s **[M]** and time-warp is 199s
> **[M]** — neither fits the slot (shotlist §3). Never let the narration imply
> either just happened on screen.

---

## CONTINGENCY BOX — decide these BEFORE recording, never mid-take

| Trigger | Action |
|---|---|
| **Fleet review runs >2 min at rehearsal** | Stop. Re-run `scripts/warmup.py --engines caseflow,treepres` to PASS, wait for the quota-quiet window, and **re-take from 0:00**. The measured attachment run is ≈62s **[M]**; the no-attachment rehearsal was 2m00s **[M]** and included a real verifier rejection and retry. A review that long overruns Segment 3 and pushes the honesty beat past the 4:00 cutoff — and only the first four minutes are judged. Do not edit; re-take. |
| **Review wait is long but under ~2 min, and you need to fill it** | Optional time-warp slot — **explicitly permitted by the video-structure ruling ("time-warp runs live-in-take if rehearsal timing allows")**. Launch `make demo-timewarp` (`CLOCK_MULTIPLIER=20000`) in a spare terminal at t≈0:52 and cut to it during 3d instead of the verifier narration. Measured 199s end to end **[M]**, so it lands ≈4:11 — treat it as *ambient* footage you narrate mid-stream ("twelve simulated days are passing in that terminal right now"), never as a completed result on camera. If it has not resumed by 3:25, drop it silently and use the recorded-evidence line in Segment 5. |
| **Live Gmail-IMAP leg unrehearsed on the day** | Use the **form feed**: the clerk console's "New application" form feeds the SAME inbox queue and is fully proven. Swap the 3a alternate line. Do not say "email" or "real email" anywhere. |
| **Concurrency (rehearse this specifically)** | This script deliberately runs the watcher, a live fleet review and `make demo-injection` against the same project quota at once — shotlist OQ3 records that concurrency as **untested**, and 429s killed a prior demo attempt. Rehearse the cluster exactly as scripted at least once. If it 429s: run the drill **after** the clerk walk instead (3f becomes the live beat), accept losing the 3c cut, and trim 3d to compensate. |
| **Case does not appear within ~20s** | Check T1 (the watcher polls every 5s). Do not press F5. If the watcher is dead, restart it — crash recovery requeues anything a dead run claimed — and re-take. |
| **Drill re-run needed** | Safe: 14/15 is stable across three consecutive runs with the same single holdout **[M]**, and the fixture used here (adv-002) is not that holdout. |
| **Drill fails entirely mid-take** | Do not splice. Say so on camera and show the recorded evidence: `docs/evidence/injection_last_run.json`, the quarantine object, and the incident already in the console. |
| **Clerk proxy drops** | The public reader renders the same approval-gate UI with controls disabled and the IAM reason stated — show that, and the existing `approvals/` row as the evidence of a real walk. |
| **Network flake anywhere in the take** | Stop, fix, re-record the whole take. Never edit. This machine's network flakes are documented (B-003) — schedule slack for 2–3 full takes. |
| **The 14/15 drill number appears on screen** | If it does, the narration MUST carry its B-014 packaging (setting `pi_and_jailbreak` ENABLED / LOW_AND_ABOVE, the four-row progression, both levers, the characterised adv-001 holdout). The script above deliberately avoids putting it on screen so the 30s eval slot does not need it. Keep it off screen. |

---

## Timing ledger

| Segment | DoD budget | Words | At 135 wpm | Δ |
|---|---|---|---|---|
| 1 Problem | 0:30 | 66 | 0:29 | −1s |
| 2 Value prop / diagram | 0:20 | 50 | 0:22 | +2s |
| 3 Live demo | ~2:00 (slot 0:50–2:55 = 2:05) | 250 | 1:51 | −14s (click/load slack) |
| 4 Eval honesty | 0:30 | 81 | 0:36 | +6s |
| 5 GCP proof | 0:40 | 84 | 0:37 | −3s |
| **Total** | **4:00** | **531** | **3:56** | **−4s** |

**Stated honestly:** segments 2 and 4 run 2–6s over the Definition-of-Done's
per-segment budgets, drawn from Segment 3's wait slack. The *beat structure*
is already ratified (video-structure ruling, 2026-08-29); these few seconds
are below the resolution of that ruling, so they are recorded here rather than
made silently. Total stays under 4:00 with a 4s reserve.

Rehearsal must measure and write back: the clerk-walk click duration
(currently **[E]** ≈20–30s, the only unmeasured number in the take), the actual
review-leg wall time on the day, and whether the diagram is legible at
recording resolution.

## Numbers spoken aloud, and where they come from

| Spoken | Source |
|---|---|
| "ten seconds — it's a case" | shotlist §2 beat D, ≈10s **[M]**, `--once` fixture drive |
| "Section 17.44.100 … verifier passed" | README "What it does" / shotlist §2 beat D — the ≈62s attachment run, verifier PASSED first pass, outcome approve |
| "zero engine calls" | `docs/evidence/injection_last_run.json`, `engine_calls_before_screen: 0` |
| "seventy-five percent … red" | `docs/eval-report.md` headline, 15/20, gate ≥85% FAIL |
| "groundedness one hundred percent" | same run, groundedness first-pass 100.00% (gate ≥95%) |
| "twelve for twelve, three runs straight" | 12-case CI smoke subset post-fix, three consecutive runs |
| "nine of nine … seven of the eight that scored" | Ablation 2, `docs/ablations.md` — text carriers only, 6 PDF fixtures excluded |
| "four agents, four least-privilege identities" | README architecture notes — per-agent service accounts + custom roles |
| "a measured hundred and ninety-nine seconds" | shotlist §2 beat C, `docs/evidence/timewarp_last_run.json`, CLOCK_MULTIPLIER=20000 |
| "registered and human-approved mid-run with nothing redeployed" | shotlist §2 beat A / `docs/evidence/demo_last_run.json` |
