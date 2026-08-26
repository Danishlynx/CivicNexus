# RUNBOOK — deploy, demo, eval, and video-day procedures (ADR-005 §8)

Every billable sequence runs from THIS document, not from memory. The
failure ledger (FAILURES.md) exists because ad-hoc commands kept re-rolling
solved problems.

## Deploy an agent (hermetic)

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

- Registry must hold ZERO approved cards (a stray card changes the
  coordinator's tool surface vs the measured baseline): run
  `scripts/demo_reset.py --confirm` first if a demo ran since.
- Archive `evals/results.json` to `evals/archive/` BEFORE any run that
  overwrites it. Never compare across configs without noting the config.
- Full runs and smoke runs each need the human's per-run OK (spend rule).

## Video day (Phase 7) — additions

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
  driver 4; verifier entailment 4. Change ONLY by amending ADR-005.
