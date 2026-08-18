# CivicNexus

**Autonomous casework, accountable by design.** A governed fleet of AI agents that
runs municipal permit cases end to end — intake, parallel department review with
mandatory code citations, groundedness verification, human approval gates, and an
immutable audit trail — built on Google Cloud (Vertex AI, ADK, Agent Engine) for
the All Things Agentic Hackathon (Fortified Enterprise Fleet track).

> **Status: Phase 0 (walking skeleton) — not yet deployed.** This README becomes
> the real spin-up guide in Phase 7, verified from a clean project. Until then,
> trust [PROGRESS.md](PROGRESS.md) for what actually works, and nothing else.

## Read first

1. [docs/PRODUCT.md](docs/PRODUCT.md) — what this is and why.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the authoritative technical spec.
3. [CLAUDE.md](CLAUDE.md) — how the build is executed.

## Layout

```
agents/     ADK agents (hello walking-skeleton agent; fleet arrives Phases 1–3)
libs/       shared Python libs — contracts (all schemas), otel (logging)
services/   FastAPI services + console (Phases 1–6)
infra/      Terraform — the only way infrastructure changes
evals/      PermitBench eval suite (Phase 2)
scripts/    deploy, smoke, phase verifiers, demo scenarios
docs/       product + architecture specs, ADRs, runbooks
```

## Working on it

Requires Python 3.12, `uv`, `make`, `terraform`, `gcloud`. Then:

```
uv sync          # install workspace + dev tools
make test        # lint, types, unit tests — PASS/FAIL
```

Deployment targets (`make bootstrap` / `deploy` / `smoke`) need a GCP project;
see the make-targets contract in [CLAUDE.md](CLAUDE.md).
