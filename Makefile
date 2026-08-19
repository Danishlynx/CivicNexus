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
	@uv lock --check && uv run ruff check . && uv run ruff format --check . && uv run mypy libs agents scripts evals && uv run pytest && echo PASS: make test || (echo FAIL: make test && exit 1)

eval-smoke:
	@uv run python -m evals.runner --tag smoke && echo PASS: make eval-smoke || (echo FAIL: make eval-smoke && exit 1)

eval-full:
	@uv run python -m evals.runner --report && echo PASS: make eval-full || (echo FAIL: make eval-full && exit 1)

demo-hotadd:
	@echo FAIL: demo-hotadd not implemented until Phase 3 && exit 1

demo-injection:
	@echo FAIL: demo-injection not implemented until Phase 5 && exit 1

demo-timewarp:
	@echo FAIL: demo-timewarp not implemented until Phase 4 && exit 1

dlq-replay:
	@echo FAIL: dlq-replay not implemented until Phase 5 && exit 1

verify-phase-0:
	@$(MAKE) test && $(MAKE) smoke && uv run python scripts/verify_phase0.py && echo PASS: make verify-phase-0 || (echo FAIL: make verify-phase-0 && exit 1)

verify-phase-1:
	@$(MAKE) test && uv run python scripts/run_case.py && echo PASS: make verify-phase-1 || (echo FAIL: make verify-phase-1 && exit 1)

verify-phase-2:
	@echo FAIL: verify-phase-2 not implemented until Phase 2 && exit 1

verify-phase-3:
	@echo FAIL: verify-phase-3 not implemented until Phase 3 && exit 1

verify-phase-4:
	@echo FAIL: verify-phase-4 not implemented until Phase 4 && exit 1

verify-phase-5:
	@echo FAIL: verify-phase-5 not implemented until Phase 5 && exit 1

verify-phase-6:
	@echo FAIL: verify-phase-6 not implemented until Phase 6 && exit 1

verify-phase-7:
	@echo FAIL: verify-phase-7 not implemented until Phase 7 && exit 1

# Guarded: judging runs until Oct 1 — teardown requires CONFIRM_TEARDOWN=YES in the environment.
teardown:
	@uv run python scripts/guard_teardown.py && $(TF) destroy -auto-approve && echo PASS: make teardown || (echo FAIL: make teardown && exit 1)
