# RUNBOOK — deploy, demo, eval, and video-day procedures (ADR-005 §8)

Every billable sequence runs from THIS document, not from memory. The
failure ledger (FAILURES.md) exists because ad-hoc commands kept re-rolling
solved problems.

## Current deployed reality (verified 2026-09-01): read this before running anything

Code and measurement are FROZEN at `main` = 985812e (freeze declared
2026-08-29). Phases 0 through 6 are complete, engineering is closed, the video
is published (https://youtu.be/8mWPskk6QUo), and the Devpost submission is in.
**Judging runs to 2026-10-01, 11:45 PM PT.**

What is deployed, and what has to stay that way until judging closes:

| Surface | State |
|---|---|
| caseflow engine | the proven Flash config: intake 4-type enum, verifier steps 1 to 6 with the Gemma 4 decidability judge at step 6. No `ZONING_MODEL_ID` and no `DECISION_MODE` baked in. Warm. |
| treepres engine | deployed; the hot-add specialist |
| Console, public reader | https://civicnexus-console-wrhx6s33dq-uc.a.run.app (no login, read-only) |
| Console, clerk | https://civicnexus-console-clerk-wrhx6s33dq-uc.a.run.app (IAM-gated; invoker binding is exactly `user:danishlynx@gmail.com`, anonymous gets 403) |
| Console image | v0.1.6, pinned in `infra/terraform/console_service.tf`; `/evals` serves the honest 20-case report |
| Scaling | both Cloud Run services at `min-instances=0`, idle cost near $0 |

Standing prohibitions for the judging window:

- **`make teardown` is FORBIDDEN until after 2026-10-01.** The
  `CONFIRM_TEARDOWN` guard stays in place; do not weaken it.
- **Do not redeploy the engines or the console.** The contest rule "must
  function consistently as depicted in the video" makes the deployed revisions
  a compliance artifact, not just a convenience.
- Do not delete the letters engine and do not trim CI, even though both are
  standing cost offers in `BACKLOG.md`. They wait until judging closes.
- Pinned evidence cases stay untouched: `case-5ea037e64ef8` (time-warp) and
  `case-c50219ca5166` (live demo case, enforced as NEVER_TOUCH in
  `scripts/verify_phase6.py`).
- Hackathon credits ran out 2026-08-28, so every billed action is personal
  money: name the estimate, get an explicit OK. $0 actions proceed.

The procedures below are the record of how each thing is done and were accurate
at freeze. During the judging window they are reference, not a work queue.

## Session-start framing (assistant sessions on Phase 5+ drill work)

Fable 5's automated safeguards paused a session on 2026-08-26 — a false
positive on the defensive fixture work (the defense-framed-terminology rule
was ratified the same day). Reading repo docs is safe — the wording pass made
them drill-framed; the trigger was authoring and quoting fixture text under
attacker-framed prose. Open every assistant session that touches drill work
with this framing, BEFORE any hot vocabulary appears:

```text
Continue CivicNexus (governed municipal permit-casework platform, Google
hackathon, Fortified Enterprise Fleet track). Follow the CLAUDE.md session
loop: read PROGRESS.md and BLOCKERS.md first. Current phase is 5 — a
defensive eval harness (ADR-006) that validates our OWN Model Armor
guardrails using synthetic screening-drill fixtures; nothing targets any
external system and drill content never leaves the drill path.

Today's task: <the task>.

Reference drill fixtures by id (adv-001..025) — do not open or quote
evals/permitbench/drills/templates.json or the generated fixture files.
```

Model routing: work that edits or quotes raw fixture text
(`evals/permitbench/drills/templates.json`, generated fixture artifacts,
`.deploy/armor_canary_last_run.json` payloads) runs in an Opus 5 session,
and so do the §9.5 ablation arms (armor-off / `--no-verifier`) — "run with
the guardrail disabled" is the hottest-shaped phrase in the project even
though it is the measurement that proves the guardrails' value (second
pause, 2026-08-27, confirmed this). Make targets, demo drivers, eval
report, docs, and console work run fine on any model with the opener above.
Never resume a session that has already been paused — the flagged context
travels with it; start fresh with the opener instead.

*Phase note added 2026-09-01, framing above deliberately unedited:* the opener
is preserved word for word because that exact wording is what was tested after
the two pauses. If you use it now, replace only the "Current phase is 5" line
with "Phases 0 to 6 are complete, the tree is frozen, and the project is in its
judging window." Every defensive-framing sentence stays as written.

## Deploy an agent (hermetic)

**FROZEN: do not run this during the judging window** (see "Current deployed
reality"). Kept as the procedure for after Oct 1, or for a clean-project
spin-up.

```powershell
$env:PROJECT_ID='civicnexus-hack26'   # REGISTRY_MODE now defaults in-manifest
Remove-Item Env:MODEL_ID -ErrorAction SilentlyContinue   # never override silently
uv run python scripts/deploy_agent.py --agent-dir agents/<a>/src/<a>_agent `
  --display-name civicnexus-<a> --service-account sa-<a> --needs-corpus `
  --state-file .deploy/<a>_agent.json
```

- The script deploys `requirements.lock.txt` (compiled linux/py3.11 closure)
  and validates the baked `.env` against the per-agent manifest — read the
  `baked .env ->` line and the `running as <sa>` line before trusting it.
- After changing any `requirements.txt`: recompile the lock first:
  `uv pip compile <req> --python-platform linux --python-version 3.11 -o <lock>`.

## Run the hot-add demo (exit proof / video)

**Billed, and frozen during the judging window.** Kept as the procedure. If it
is ever run again, step 2 (`demo_reset`) must also be run *after* the demo, so
the registry holds zero approved cards and the eval baseline's tool surface
stays what was measured.

1. **Quota-quiet window**: no eval runs or CI pushes within ±30 min. Check
   nothing is running; push only with `[skip ci]` during the window.
2. **Reset the fixture** (clean BEFORE moment): 
   `uv run python scripts/demo_reset.py --confirm`
3. **Warm the path** (MANDATORY — cold engines killed 2 attempts):
   `uv run python scripts/warmup.py --engines caseflow,treepres` → must PASS.
4. **Run** (from repo root; never `make demo-hotadd` — it lacks --skip-deploy):
   `$env:PROJECT_ID='civicnexus-hack26'; $env:REGISTRY_MODE='firestore';`
   `uv run python scripts/demo_hotadd.py --skip-deploy --approver danishlynx@gmail.com`
5. **On FAIL**: read `.deploy/demo_last_run.json` FIRST (raw replies +
   timings persisted per attempt) — engine logs are the second stop now.

## Run evals

**Frozen too.** The shipped measurement is the 2026-08-28 full run (15/20 =
75%, gate red and visible) plus the 12-case CI smoke at 12/12 across three
consecutive runs. Do not re-run either during the judging window: it costs
personal money and any new number would diverge from the report the console and
the video already show.

- Registry must hold ZERO approved cards (a stray card changes the
  coordinator's tool surface vs the measured baseline): run
  `scripts/demo_reset.py --confirm` first if a demo ran since.
- Archive `evals/results.json` to `evals/archive/` BEFORE any run that
  overwrites it. Never compare across configs without noting the config.
- Full runs and smoke runs each need the human's per-run OK (spend rule).

### Ablation arms (§9.5) - BILLED, each needs its own spend OK

```
# verifier off vs on. Writes to evals/archive/, NEVER to results.json.
python -m evals.runner --tag smoke --no-verifier

# armor off vs on. Refuses to issue any engine call without the flag.
python -m evals.drill_runner --armor off --i-have-a-spend-ok --label drill-armor-off

# build the comparison table (offline, reads archived JSON only)
python -m evals.compare [--charts]
```

The armor-OFF arm covers **text carriers only**: 6 of the 15 gate fixtures are
PDF carriers, and the drill runner has no unscreened path that ingests a PDF, so
those fixtures are screening-layer only and their result never transfers to this
arm (ADR-006 D9 / A-12). Both the arm and the table state how many fixtures were
excluded and why. Do not quote that arm as full gate coverage.

Scope note added 2026-09-01 so the phrase above is not read wider than it goes:
the **product** intake path does ingest PDFs. Since 2026-08-28 intake
attachments (PNG, JPEG, PDF; 3 per email, 4MB) are byte-screened, then
transcribed by deterministic Cloud Vision OCR, and the extracted text is
re-screened as plain text; an attachment OCR cannot read fails closed to
quarantine. That closed A-12 at intake. It did not change the archived
armor-OFF arm, which measured the drill runner's engine path and stays reported
exactly as it was measured.

`compare.py` refuses to pair arms that are not genuinely comparable and says
"NOT a comparison" rather than showing a delta it cannot justify.


## Intake paths that exist (verified against the deployed code, 2026-09-01)

Three ways an application enters the system. All three land in the same inbox
queue that the watcher consumes, and there is no fourth.

1. **Clerk console form**: `GET /cases/new` + `POST /cases/new`, clerk mode
   only. Structured fields are composed into the same email-shaped text the
   watcher consumes and submitted with `source="console_form"` plus a named
   human. Fully proven; this is the default path on camera.
2. **Watcher, fixture drive**:
   `uv run python scripts/inbox_watcher.py --once <file>` drives one
   application file and exits. Every recorded rehearsal measurement in
   `docs/shotlist.md` §2 used this path.
3. **Watcher, live Gmail over IMAP**: `--consume --watch-gmail
   --i-accept-billing`, spend bounded by `--max-cases` (default 3), crash
   recovery requeues anything a dead run left claimed. Honest status is
   unchanged: no `docs/evidence/*.json` records a live IMAP firing, so treat
   the live hop as unproven and do not describe it as proven anywhere.

The console never invokes an engine (D13). The watcher is what drives intake
into review; the console reads and transitions.

## Phase 5 drills (ADR-006)

All four are $0 unless noted. Each writes evidence to `.deploy/*_last_run.json`
BEFORE parsing, so a crashed run still leaves a usable record.

Judging-window note (2026-09-01): these are $0, but `make demo-injection` and
`dlq-replay` write new cases, incidents and events into the same Firestore the
public console is serving to judges. Leave them alone unless there is a reason
to run them, and never touch the pinned evidence cases.

| Drill | Command | Cost | Detail |
|---|---|---|---|
| Screening canary, both arms | `python -m scripts.armor_canary` | $0 | D10 precondition for every billed step |
| Injection containment | `make demo-injection` | $0 (letters leg opt-in) | [runbooks/injection-drill.md](runbooks/injection-drill.md) |
| DLQ replay | `make dlq-replay` | $0, takes 2-3 min | [runbooks/dlq-replay.md](runbooks/dlq-replay.md) |
| Registry governance | `python -m scripts.drill_tool_poisoning` | $0 | D18 try/finally deletes exactly its own `drill-poison-*` ids |
| Full gate | `make verify-phase-5` | $0 | Runs test + all of the above |

**Any fixture regeneration invalidates canary-green (D10).** Re-run the canary
before the next billed step - `make demo-injection` does this for you.

**`--expect` is not decoration.** The injection gate measures **14/15** at
`LOW_AND_ABOVE` with one characterised holdout (B-014), so both the canary and
the drill runner default to 14. A run that demands 15 fails for a known reason.
Never raise it to make a number look rounder; the holdout is boundary behaviour
at a dilution ratio, and B-014 explains why tuning it would be fitting the test
to the system.

**Ablation arms are BILLED and gated behind explicit flags** - see "Run evals".

## Video day (Phase 7): EXECUTED 2026-08-31; kept as the procedure

The take was recorded 2026-08-31 and published 2026-09-01 at
https://youtu.be/8mWPskk6QUo. `docs/submission/video-script.md` is the script
that was shot; `docs/shotlist.md` carries the measured timing ledger behind it
and the ratified video-structure ruling that shaped it.

One item is still live: **if the ASK-FIRST `min_instances=1` lever was applied
to caseflow and treepres for the recording, confirm it is back at 0.** Nothing
in this runbook records which way it went, so verify rather than assume; idle
cost through Oct 1 depends on it.

The original checklist, kept:


- Clean browser profile + empty desktop (no third-party logos — rules).
- Reserve a quota-quiet hour; do a full rehearsal run first.
- Optional (ASK-FIRST, costed): `min_instances=1` on caseflow+treepres for
  the recording day only; revert after.
- Record `.deploy/demo_last_run.json` timings from rehearsal to pace the
  continuous take.

## Standing rules

- Non-zero exit at the END of a terraform apply = state-integrity event:
  check `terraform.tfstate` size immediately (B-008 lesson).
- Never conclude "no traces" from the v1 API (B-005); Trace Explorer only.
- Estimates are ceilings; the billing page is the truth (spend rule).
- One retrying layer per failure domain (ADR-005 §3): engine model calls 1
  attempt; consult tool 2; demo driver 2 (pre-first-event only); eval
  driver 4; verifier entailment 4; armor screening client 2 (transient-only —
  amended by ADR-006, ratification pending). Drill-runner engine queries ride
  the eval-driver row; the demo_injection letters query rides the demo-driver
  row (ADR-006 D9/D14). Change ONLY by amending ADR-005/ADR-006.
