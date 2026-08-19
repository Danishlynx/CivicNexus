# Walkthrough: how Phases 0 and 1 were built

Written for Danish's gate review. Read top to bottom; ~20 minutes plus poking
around. AWS analogies included since that's home turf.

## The one-paragraph story

Phase 0 built the *walking skeleton*: a repo where every check is executable
(`make test`), all infrastructure comes from Terraform (like CloudFormation,
but the only allowed path), and one trivial AI agent deployed to **Agent
Engine** (think: Lambda for AI agents — Google runs the container, scales it,
bills per use) proving the deploy + tracing path works. Phase 1 built the
*vertical slice*: a real municipal law corpus, a Firestore case database with
a strict state machine, and a three-agent fleet (intake → coordinator →
zoning) that took a synthetic applicant's messy email and produced a legally
cited determination now sitting in `PENDING_HUMAN` — waiting for a clerk.

## Reading order

1. [PROGRESS.md](../PROGRESS.md) — what's done, with evidence. The honest ledger.
2. [docs/adr/001](adr/001-live-docs-deltas-at-build-start.md) and
   [002](adr/002-phase1-platform-deltas.md) — every place reality differed
   from the spec, and what we did about it. **The most useful files for
   understanding *why* things look the way they do.**
3. [BLOCKERS.md](../BLOCKERS.md) — every problem hit, and how each resolved.
4. `git log --oneline` — 30+ small commits, each one story-sized.

## Map of the repo (and the AWS translation)

| Path | What it is | AWS analog |
|---|---|---|
| `infra/terraform/` | ALL infrastructure: 21 APIs, budget alerts (INR!), Pub/Sub topics, Firestore DB, BigQuery audit sink, IAM | CloudFormation/CDK stack |
| `libs/contracts/` | Every schema in the system as Pydantic models: events, Case, Determination, the 13-state machine | Shared types package |
| `libs/otel/` | Structured JSON logging that Cloud Logging parses natively; `audit: true` lines flow to BigQuery | CloudWatch structured logs + Firehose to Redshift |
| `libs/tools/` | The **case store** — the only code allowed to change case state; enforces the state machine, human-only gates, approval requirements | DynamoDB DAO with transactional guards |
| `agents/caseflow/` | The fleet: coordinator (router) + intake (parser) + zoning (reviewer with the code-lookup tool) | — no real analog; closest is Step Functions where the steps think |
| `data/corpus/` | 37 sections of Monrovia CA's real zoning code, one file per section — filenames ARE the citation keys | The knowledge base S3 bucket |
| `scripts/` | deploy, smoke, seed_corpus, run_case (the e2e driver), phase verifiers | deploy/ops scripts |
| `evals/` | doesn't exist yet — that's Phase 2 | — |

## The five decisions worth understanding

1. **Tests define done, dishonesty is impossible-by-default.** Every `make`
   target prints PASS/FAIL; unimplemented ones FAIL loudly naming their phase.
   A multi-agent review audited the scaffold and found 30 real issues
   (including `make` with no args running `terraform apply` — now it prints help).
2. **The case store is the single writer.** Agents never touch Firestore;
   they return findings, and the store refuses illegal transitions, non-human
   approvals, and unapproved DENY/ISSUE. The security model starts in the data
   layer, not in prompts.
3. **Citations are file identities.** RAG retrieval gives back no chunk IDs
   (verified empirically), so the corpus is one-file-per-code-section and the
   filename (`17.44.100`) is the citation key. The e2e driver then re-checks
   every quote *verbatim* against the committed text — an agent cannot invent
   a law.
4. **Model calls route globally, everything else stays in us-central1.**
   Gemini 3.x wouldn't serve regionally on this project (probed: HTTP 417).
   Data, storage, deployment stay regional; only inference goes via the
   global endpoint. ADR-001 item 8.
5. **Deploy via the ADK CLI, not the SDK.** Three tracing mechanisms were
   tried; the CLI source-build path is the one wired for telemetry, and
   SDK-built vs CLI-built instances can't update each other (ADR-001 item 9).

## See it live (5 minutes)

- **A real case:** Firestore console →
  https://console.cloud.google.com/firestore/databases/-default-/data/panel/cases?project=civicnexus-hack26
  — open any `case-…` doc: `state: PENDING_HUMAN`, and inside
  `determinations[0].citations` the section number + verbatim quote.
- **The traces:** https://console.cloud.google.com/traces/explorer?project=civicnexus-hack26
  — spans for every agent invocation and model call.
- **The agent itself:** Agent Engine playground →
  https://console.cloud.google.com/vertex-ai/agents/agent-engines/locations/us-central1/agent-engines/2118760555991793664/playground?project=civicnexus-hack26
  — paste `{"task": "review", "application": {"applicant_name": "Test", "applicant_email": "t@example.test", "permit_type": "garage_conversion", "project_description": "convert garage to a woodworking shop with two employees", "property_address": "1 Demo St", "missing_items": [], "complete": true}}`
  and watch it look up the law and rule.
- **Run the whole pipeline yourself** (costs ~$0.02):
  ```powershell
  $env:PROJECT_ID = 'civicnexus-hack26'
  uv run python scripts/run_case.py
  ```
- **The bill:** https://console.cloud.google.com/billing — total so far ≈ $1.

## What Phase 2 will do (when you give the go)

"Evals first": ~20 golden cases (scripted, reproducible), a runner that drives
the deployed stack, metrics (decision accuracy, citation precision,
groundedness), a CI gate so regressions can't merge, and baseline numbers —
including an answer to the one open behavioral question: the zoning agent gave
`deny` and `request_info` on the same facts in two runs; Phase 2 measures that
variance and Phase 5's verifier clamps it.
