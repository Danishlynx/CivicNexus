# Devpost submission — ready to paste

**Category / track:** Fortified Enterprise Fleet

---

## Project name

**CivicNexus**

## Tagline (one line)

Autonomous casework, accountable by design — a governed agent fleet that runs a
municipal permit case end to end, and cannot sign anything without a named
human.

---

## Inspiration

A building permit is a multi-department decision made from messy inputs —
half-filled forms, scanned PDFs, a crooked phone photo of a floor plan — under
written rules, stretched across weeks of silence while the applicant responds.
Somebody wants to convert their garage into a small bakery, and the answer is
already sitting in the municipal code. They still wait, sometimes through weeks
or months of backlog.

Nobody in that loop is lazy. The clerk is the message bus: they print, check
completeness, route the file to each department in sequence, relay every
question, and re-read everything each time a reply lands. Their day is reading
and routing. It is almost never deciding.

So the target was never "replace the clerk." It was: give the reading to
machines, keep the deciding human, and make the machine's half more auditable
than the manual process ever was. Governance is not a checkbox bolted onto the
end of this product — it *is* the product.

## What it does

An application arrives by email or through the clerk's intake form.
Attachments are allowlisted (PNG/JPEG/PDF, 3 per email, 4 MB cap), byte-screened
by Model Armor, transcribed by deterministic Cloud Vision OCR, and **screened
again as plain text before any model sees them**. A coordinator agent triages
the case and fans out to specialist reviewers. Every determination must carry
verbatim citations to the municipal code, which a groundedness verifier checks
byte-exact against the committed corpus; a failure triggers critique-and-retry,
and the verifier's report — pass or fail — travels with the case to the human.

Then the case stops. Only a named human, through an IAM-gated clerk console,
can approve, deny, issue or close it. Issuing requires a **write-once
`approvals/` row** that the single-writer `CaseStore` verifies inside the
transition guard — so a permit literally cannot exist without a row naming who
signed it.

Measured on the deployed stack (2026-08-28): a demo application with a
floor-plan attachment went from `case.received` to the human gate with a
verifier-passed, §17.44.100-cited approve recommendation in **~62 seconds**,
with the attachment OCR'd and screened en route.

And when it is attacked, it handles it alone. A drill email carrying hostile
override text present **only as pixels in a screenshot** (byte-verified absent
from the file's bytes) was OCR-transcribed, matched at HIGH confidence by the
plain-text screen, and taken RECEIVED → QUARANTINED with the bytes held in a
locked bucket, one incident raised, and one traceparent across all three audit
events. **Zero engine calls. Zero human involvement.** That case
(`case-1216f7712d35`) and its incident metadata are on the live console right
now.

## How we built it

Everything is Google Cloud, and the infrastructure is Terraform-only — no
console click-ops.

- **Vertex AI Agent Engine + ADK** — four deployed agents (`caseflow`
  coordinator/intake/zoning, `safety`, `letters`, `treepres`), each running as
  its own least-privilege service account with a custom role. Agent-to-agent
  access is per-resource IAM, and a deliberate-deny test produced an audited
  403. `treepres` was registered and human-approved **mid-run** through the
  registry with nothing redeployed.
- **Gemini** (`gemini-3.5-flash`) for coordination, intake and review.
- **Gemma 4 (26B, Vertex AI managed API)** as the **decidability judge** in the
  verification layer — the step that asks whether a request for more
  information is even warranted. Model diversity is the point: the Gemini Flash
  entailment judge measurably co-signed that failure class. It is hardened
  against two properties we measured live on that surface — temp-0
  nondeterminism (five identical calls flipped the verdict 1 in 5) and
  `response_schema` accepted but not enforced — using 2-of-2 self-agreement
  plus byte-level verification of every quote it produces.
- **Cloud Vision** for deterministic OCR at intake — a transcription engine,
  not a chat model, so pixels cannot instruct it.
- **Model Armor** at four screening points (`inbound_content`, `worker_output`,
  `letter_draft`, `memory_write`), all four live-measured.
- **Firestore** as the single-writer case store, write-once inbox queue,
  write-once approvals, incidents and agent registry. **Pub/Sub** (12 topics,
  one per event type), **Cloud Tasks** for long timers, **Cloud Run** for the
  registry and both console services, **Cloud Build** for images, **BigQuery**
  for the audit log sink, **Cloud Trace** for OTel spans.
- **Vertex AI RAG** over one chapter of a real public municipal code (City of
  Monrovia, CA, Title 17 Ch. 17.44 "Special Uses", 37 sections, attributed in
  `data/CORPUS_SOURCE.md`), and **Vertex AI Memory Bank** for recall across
  multi-week gaps.
- Python 3.12, `uv` workspace, `ruff` + strict `mypy`, Pydantic contracts as
  the single source of truth for every schema. Current gate: **331 passed, 14
  skipped, 90.23% coverage**.

The whole thing was built under a written working agreement with phase gates,
ask-first rules for IAM/spend/guardrail changes, and a truthfulness-first
evidence log. Two Cloud Run consoles enforce the split: a **public reader**
whose service account holds exactly one Google Cloud role
(`roles/datastore.viewer`) — it cannot write, cannot spend, cannot publish, and
cannot read a quarantined document regardless of what its code does — and an
**IAM-gated clerk** where approvals actually happen.

## Challenges we ran into

**We shipped a failing grade on our own public page, for weeks.** The
decision-accuracy gate is ≥85%. Five full runs measured 65–80%. We never
lowered the threshold, and `/evals` renders the eval report unedited whatever
the gate says — so the red number was public the entire build.

**Outcome variance was real and it was ours.** Identical facts produced `deny`
on one run and `request_info` on the next, at temperature 0, on the same
config. Both readings are defensible under the statute. We characterised the
wobble instead of averaging it away, and every claim in this project carries
its run-to-run spread.

**We measured our way out instead of guessing.** Two levers were run as real
experiments, pre-committed and archived:

- **Gemini 2.5 Pro at the decision step.** A statute-level study predicted two
  of five misses were model-fixable. Both converted — and **Pro scored the same
  15/20**, regressing a solid deny and failing one case on output-schema
  compliance, with groundedness dropping below its gate and ~50% higher
  latency. Measured conclusion: **model tier is not the constraint.**
- **"The model extracts, code decides"** (ADR-008) — a full rules engine, 14
  corpus sections, 82 elements, passing 20/20 offline. Live it measured
  **11/20** and was reverted under a threshold pinned *before* the run.
  Composition determinism turned out to be necessary but not sufficient; the
  real frontier is which sections extraction engages.

Both artifacts are archived in `evals/archive/`. Neither is a shipped claim.

**The freeze-eve defect hunt.** The day before freeze, artifact-level failure
recording finally exposed a real bug rather than a model wobble: intake's
instruction still enumerated exactly one permit type from an early phase, so
off-enum cases missed the config lookup, the verifier's legality step failed
every outcome, and its misleading critique **corrupted retries** — measurably
flipping one correct finding wrong. We fixed it. The 12-case CI smoke subset
then measured **12/12 three consecutive times**. The 8 held-out harder cases
measured 3/8 in the same run, which is what put the remaining failure exactly
where it belongs: model decision behaviour on hard cases, split into
over-asking and over-deciding, with every miss named by id in the report.

**The honest verifier result.** Our retry loop cost 2.5× the tokens and
corrected **zero of the seven** findings it retried. We published that. What
the verifier actually buys, measured, is citation fidelity — groundedness
first-pass 100% vs 91.7% with it off, citation precision 91.7% vs 87.5% — and
that is the claim we make for it, not decision correction.

## Accomplishments we're proud of

Every number below is scoped to the run that produced it.

- **~62 seconds**, measured on the deployed stack, from `case.received` to a
  verifier-passed, §17.44.100-cited determination at the human gate — with a
  floor-plan attachment OCR'd and screened en route.
- **A hostile screenshot contained autonomously**: pixels OCR'd, matched, case
  quarantined byte-identical, incident raised, one trace id across all three
  audit events — **zero engine calls, zero human involvement**.
- **Groundedness first-pass 100%** on the shipped full run (gate ≥95%);
  **canary leak rate 0.00%** in every eval run and both ablations.
- **9/9 drill fixtures blocked** with screening on, none reaching a model —
  against **7 of the 8 that scored** steering the fleet to approve with
  screening off. Scope, stated: text carriers only (6 PDF-carrier fixtures have
  no unscreened ingestion path), and there is no no-injection control arm, so
  the OFF number is a strong indicator, not proof of obedience.
- **CI smoke gate 12/12, three consecutive runs** after the freeze-eve fix.
- **75% (15/20) full-set accuracy shipping RED** on a public page with every
  miss named — the threshold was never touched.
- **Per-agent least-privilege IAM** with an audit-backed deliberate-deny test.
- **Runtime hot-add**: a new specialist registered and human-approved mid-run,
  routed to by the coordinator, nothing redeployed (recorded evidence).
- **12-day time-warp resume** via Memory Bank, measured **199s** at
  `CLOCK_MULTIPLIER=20000`, including an honest control probe showing the case
  cannot complete *without* the recalled facts.
- **A permit that cannot exist without a name on it** — write-once approvals
  row, verified inside the store's transition guard.

## What we learned

**Model tier was not the constraint. Neither was determinism alone.** We
measured both, and both came back "no." That is a more useful finding than
either would have been if it had worked, and we only have it because the
thresholds were pinned before the runs.

**A gate that never fires costs nothing and proves nothing, and both halves of
that are true.** Our Gemma decidability judge fired zero times in its one
full-run measurement. It ships as conservative defense-in-depth, described as
exactly that.

**Instrumentation beats intuition.** Weeks of "the model is being weird"
dissolved the moment artifact-level failure recording made one case's failure
readable. The bug was a stale enum in a prompt.

**Honesty is a load-bearing feature, not a disclosure section.** Publishing the
red gate is what forced the root-cause hunt that fixed it. A project that hides
its failing number never gets to fix it.

## What's next

- **The extraction-scoping frontier (ADR-008).** The live code-decides run
  failed by *over-engaging inapplicable sections*, not by mis-composing.
  Section-level applicability is now the named next problem, with the
  measurement plan already written down.
- Close the remaining OCR blind spot: raster text beyond a PDF's fifth page.
- Add a no-injection control arm so the screening ablation becomes proof rather
  than indicator.
- Scale shape (deliberately deferred, not architectural): indexed limit queries
  and cursor pagination on the console queue, and parallel Cloud Tasks
  consumers to replace the single serial watcher. The **human gate stays the
  throughput ceiling** — that is the product, not a bug.
- Re-verify clean-project spin-up end to end. It is assembled from a verified
  build history but has not been re-run from scratch, and the README says so.

## Try it

**Public console (read-only, no login):**
https://civicnexus-console-wrhx6s33dq-uc.a.run.app

Judges can click, with nothing staged:

- the **live case queue**, which updates itself;
- full **case dossiers** — determinations, verbatim code citations, and the
  verifier's report, pass or fail;
- the **incident view** (metadata only — quarantined bytes are never served),
  including `case-1216f7712d35`, the pixel-only hostile screenshot the system
  contained by itself;
- **`/evals`**, which renders our eval report **unedited whatever its gate
  status** — you will land on a red 75% with every failing case named;
- a **closed case** still browsable, whose page explains the write-once
  `approvals/` row (`approvals/apr-ea2cfd823116`) that lives in Firestore as
  the durable evidence of the human clerk walk. Stated precisely: the console
  explains that row rather than rendering its contents — no reader route serves
  approvals data.

The reader's service account holds a single role (`roles/datastore.viewer`), so
it cannot write, spend, publish, or read a quarantined document.

**Clerk console** (where approvals actually happen) is IAM-gated to a single
named human. **Judge access is offered on request** — granted by adding your
Google identity as an invoker on the clerk service, not by sharing credentials.
The public page renders the same approval-gate UI with controls disabled and
the IAM reason stated.

All data on the site is synthetic (faker, fixed seeds). Strings like `CANARY-*`
are deliberately planted leak detectors, not mistakes — every page footer
explains this.

**Repo:** `<REPO URL>` — README carries the architecture diagram, the full
results table, a failure-modes section, the AI-assistance and
pre-existing-code disclosure, corpus attribution, and `THIRD_PARTY.md`.
**Video:** `<YOUTUBE URL>`

## Built with

`google-cloud` · `vertex-ai` · `vertex-ai-agent-engine` ·
`agent-development-kit` · `gemini` · `gemma` · `cloud-vision` · `model-armor` ·
`vertex-ai-rag` · `vertex-ai-memory-bank` · `firestore` · `pub-sub` ·
`cloud-tasks` · `cloud-run` · `cloud-build` · `bigquery` · `cloud-trace` ·
`opentelemetry` · `terraform` · `python` · `uv` · `pydantic` · `fastapi` ·
`uvicorn` · `jinja2` · `ruff` · `mypy` · `pytest`

---

## Disclosure block (paste wherever Devpost asks, or append to "How we built it")

CivicNexus was built with **Claude Code** (Anthropic) as the build agent,
working under a human-ratified process: phase gates with human review,
ask-first rules for IAM, spend and guardrail changes, and a truthfulness-first
evidence log. The human operator reviewed and ratified every architecture
decision, authorized every infrastructure apply, and personally performed the
clerk approvals. No pre-existing code beyond the open-source dependencies
listed in `THIRD_PARTY.md`. The municipal code corpus is one chapter of a real
public code (City of Monrovia, CA), retrieved once by hand and attributed in
`data/CORPUS_SOURCE.md`; no scraper ships with the repo and no affiliation or
endorsement is implied. All application data is synthetic. The adversarial
fixtures (`adv-001..025`) are synthetic screening-drill inputs that exist
solely to validate CivicNexus's own guardrails; they target nothing external
and never leave the drill path.
