# THIRD_PARTY — direct dependencies and their licenses

Direct dependencies as declared in the workspace `pyproject.toml` files
(root, `libs/*`, `agents/*`, `services/*`), with version constraints as
pinned there. Exact resolved versions are in `uv.lock`. Licenses were
verified 2026-08-28 against the installed package metadata
(`.venv/Lib/site-packages/*.dist-info/METADATA`) and, for the standalone
tools, against the upstream LICENSE file at the installed version's release
tag; the verified resolved version is noted where the license depends on it.

## Runtime dependencies

| Package | Constraint | Declared in | License |
|---|---|---|---|
| pydantic | >=2.7 | libs/contracts | MIT |
| PyYAML | >=6.0 | libs/contracts | MIT |
| google-adk | >=2.7,<3 | agents/* (hello, caseflow, safety, letters, treepres) | Apache-2.0 |
| google-genai | >=1.0 | libs/verifier | Apache-2.0 |
| google-cloud-firestore | >=2.16 | libs/tools, services/registry, services/console | Apache-2.0 |
| google-cloud-pubsub | >=2.21 | libs/tools | Apache-2.0 |
| google-cloud-tasks | >=2.24.0 | root | Apache-2.0 |
| fastapi | >=0.115 | services/registry, services/console | MIT |
| uvicorn | >=0.30 | services/registry, services/console | BSD-3-Clause |
| jinja2 | >=3.1 | services/console | BSD-3-Clause |
| python-multipart | >=0.0.9 | services/console | Apache-2.0 |

Note on call-time imports not declared as direct dependencies:

- `libs/tools` (armor REST client, Cloud Vision OCR client) imports
  `google.auth` and `requests` at call time — they arrive transitively via the
  `google-cloud-*` packages. google-auth is Apache-2.0; requests is
  Apache-2.0.
- `scripts/inbox_watcher.py` (quarantine path) and `scripts/demo_injection.py`
  import `google-cloud-storage` at call time — declared in no workspace
  `pyproject.toml`; it arrives transitively via the dev-group
  `google-cloud-aiplatform` SDK. Apache-2.0 (verified from the installed
  3.13.1 metadata).

If strictness is wanted, declare all three explicitly before submission
(`google.auth` + `requests` in `libs/tools`; `google-cloud-storage` where the
scripts' runtime env is defined).

## Development / eval / fixture-generation dependencies (dev group, root)

| Package | Constraint | Purpose | License |
|---|---|---|---|
| ruff | >=0.6 | lint + format | MIT |
| mypy | >=1.11 | strict type checking | MIT |
| pytest | >=8.3 | test runner | MIT |
| pytest-cov | >=5.0 | coverage gate | MIT |
| pre-commit | >=3.8 | hook runner | MIT |
| types-pyyaml | >=6.0 | mypy stubs | Apache-2.0 (verified, installed 6.0.12.20260815) |
| google-cloud-aiplatform[agent_engines,adk] | >=1.112 | Agent Engine deploy SDK | Apache-2.0 |
| pandas | >=2.0 | required by the agentplatform rag surface | BSD-3-Clause |
| faker | >=26.0 | synthetic PII, fixed seeds | MIT |
| reportlab | >=4.2 | drill-corpus PDF fixtures (invariant mode) | BSD (verified from the installed 5.0.1 metadata: "BSD license", OSI-approved BSD classifier; exact clause form per its bundled license.txt) |
| pillow | >=10.4 | image fixture rendering | MIT-CMU (verified from the installed 12.3.0 metadata) |
| types-reportlab | >=4.2 | mypy stubs | Apache-2.0 (verified, installed 4.5.1.20260807) |

## Tooling (not Python packages)

| Tool | Use | License |
|---|---|---|
| Terraform | all infrastructure | BUSL-1.1 (verified against the hashicorp/terraform v1.15.8 LICENSE — the installed version; Change License MPL-2.0) |
| gitleaks | secret scanning in pre-commit/CI | MIT (verified against the gitleaks v8.30.1 LICENSE — the installed version) |
| uv | package/workspace manager | Apache-2.0 OR MIT, at your option (verified against astral-sh/uv 0.12.1 — the installed version) |

## Data

- Municipal code corpus: City of Monrovia, CA, Municipal Code, Title 17,
  Chapter 17.44, via the American Legal Publishing Code Library — public
  record, used as reference material only. Full attribution and disclaimer in
  `data/CORPUS_SOURCE.md`.
- All other data (applicants, cases, drill fixtures) is synthetic, generated
  in-repo with faker under fixed seeds.

Workspace-internal packages (`civicnexus-*`) are first-party code written for
this hackathon and are not third-party.
