# CivicNexus make targets — contract in CLAUDE.md. Every target prints PASS or FAIL.
# Recipes are single-line so they run identically under cmd.exe and sh.

TF := terraform -chdir=infra/terraform

# Bare `make` must never touch infrastructure — bootstrap applies billed resources.
.DEFAULT_GOAL := help

.PHONY: help bootstrap deploy smoke test eval-smoke eval-full demo-hotadd demo-injection \
        demo-timewarp dlq-replay teardown verify-phase-0 verify-phase-1 verify-phase-2 \
        verify-phase-3 verify-phase-4 verify-phase-5 verify-phase-6 verify-phase-7

help:
	@echo Targets (contract in CLAUDE.md): bootstrap deploy smoke test eval-smoke eval-full demo-hotadd demo-injection demo-timewarp dlq-replay verify-phase-N teardown

bootstrap:
	@$(TF) init -input=false && $(TF) apply -input=false -auto-approve && uv run python scripts/check_bootstrap.py && echo PASS: make bootstrap || (echo FAIL: make bootstrap && exit 1)

deploy:
	@uv run python scripts/deploy_hello.py && echo PASS: make deploy || (echo FAIL: make deploy && exit 1)

smoke:
	@uv run python scripts/smoke.py && echo PASS: make smoke || (echo FAIL: make smoke && exit 1)

test:
	@uv lock --check && uv run ruff check . && uv run ruff format --check . && uv run mypy libs agents scripts evals services && uv run pytest && echo PASS: make test || (echo FAIL: make test && exit 1)

eval-smoke:
	@uv run python -m evals.runner --tag smoke && echo PASS: make eval-smoke || (echo FAIL: make eval-smoke && exit 1)

eval-full:
	@uv run python -m evals.runner --report && echo PASS: make eval-full || (echo FAIL: make eval-full && exit 1)

# Needs PROJECT_ID env, APPROVER=<human email> make-var, and either
# REGISTRY_URL or REGISTRY_MODE=firestore (B-007 interim, ADR-003 addendum).
# Each run deploys/uses billable resources - run with the human's OK.
demo-hotadd:
	@uv run python scripts/demo_hotadd.py --approver $(APPROVER) && echo PASS: make demo-hotadd || (echo FAIL: make demo-hotadd && exit 1)

# Needs PROJECT_ID. The $0 canary is a printed precondition (ADR-006 D10).
# The letters leg is billable and OFF by default: add --with-letters with an OK.
demo-injection:
	@uv run python -m scripts.armor_canary --arm positive && uv run python -m scripts.demo_injection $(DEMO_ARGS) && echo PASS: make demo-injection || (echo FAIL: make demo-injection && exit 1)

# Needs PROJECT_ID and CLOCK_MULTIPLIER (e.g. 20000 = 12 days in ~52s).
# Billable (engine queries + memory ops) - run with the human's OK per RUNBOOK.
demo-timewarp:
	@uv run python scripts/demo_timewarp.py && echo PASS: make demo-timewarp || (echo FAIL: make demo-timewarp && exit 1)

# Needs PROJECT_ID. Pub/Sub only - no engine calls, so effectively $0.
dlq-replay:
	@uv run python -m scripts.dlq_replay && echo PASS: make dlq-replay || (echo FAIL: make dlq-replay && exit 1)

verify-phase-0:
	@$(MAKE) test && $(MAKE) smoke && uv run python scripts/verify_phase0.py && echo PASS: make verify-phase-0 || (echo FAIL: make verify-phase-0 && exit 1)

verify-phase-1:
	@$(MAKE) test && uv run python scripts/run_case.py && echo PASS: make verify-phase-1 || (echo FAIL: make verify-phase-1 && exit 1)

verify-phase-2:
	@echo FAIL: verify-phase-2 not implemented until Phase 2 && exit 1

verify-phase-3:
	@echo FAIL: verify-phase-3 not implemented until Phase 3 && exit 1

verify-phase-4:
	@$(MAKE) test && $(MAKE) demo-timewarp && echo PASS: make verify-phase-4 || (echo FAIL: make verify-phase-4 && exit 1)

# Phase 5 exit criteria (ARCHITECTURE §11, scoped by ADR-006). The $0 legs run
# unconditionally; the billable demo legs are opt-in via DEMO_ARGS so the gate
# can be re-checked without spend. Pass EXPECT=<n> to state the injection
# denominator explicitly - it is 14/15 today with one characterised holdout
# (B-014), so this target never hardcodes a number it did not measure.
verify-phase-5:
	@$(MAKE) test && uv run python -m scripts.armor_canary && uv run python -m evals.drill_runner --expect $(or $(EXPECT),14) && uv run python -m scripts.drill_tool_poisoning && $(MAKE) dlq-replay && echo PASS: make verify-phase-5 || (echo FAIL: make verify-phase-5 && exit 1)

# Phase 6 exit (ADR-007 §4): $0 - HTTP + Firestore only, no engine calls.
# Needs PROJECT_ID, CONSOLE_URL (public reader), CONSOLE_CLERK_URL (private);
# clerk auth is the caller's own gcloud identity token.
verify-phase-6:
	@$(MAKE) test && uv run python scripts/verify_phase6.py && echo PASS: make verify-phase-6 || (echo FAIL: make verify-phase-6 && exit 1)

verify-phase-7:
	@echo FAIL: verify-phase-7 not implemented until Phase 7 && exit 1

# Guarded: judging runs until Oct 1 — teardown requires CONFIRM_TEARDOWN=YES in the environment.
teardown:
	@uv run python scripts/guard_teardown.py && $(TF) destroy -auto-approve && echo PASS: make teardown || (echo FAIL: make teardown && exit 1)
