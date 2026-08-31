# Devpost submission — ready to paste

**Category / track:** Fortified Enterprise Fleet

---

## Project name

**CivicNexus**

## Tagline (one line)

A governed fleet of AI agents that runs a municipal permit case end to end, and
cannot sign anything without a named human.

---

## Inspiration

If you have ever applied for a building permit, you know the shape of it. You
send in a form, maybe a scanned PDF and a crooked phone photo of your floor
plan, and then you wait. Weeks. Sometimes months. And usually the answer was
already sitting in the municipal code the whole time. Somebody just had to read
it.

Nobody in that loop is being lazy. The clerk prints the file, checks it is
complete, routes it to each department in turn, relays every question back to
the applicant, and re-reads the whole thing every time a reply lands. That is
the job: reading and routing. Almost never deciding.

So we never set out to replace the clerk. We wanted to hand the reading to
machines, keep the deciding with a person, and make the machine's half of the
work more auditable than the paper process ever was.

## What it does

An application arrives, either by email or through the clerk's intake form. If
it has attachments, they get allowlisted (PNG, JPEG or PDF, up to three per
email, 4 MB each), screened as raw bytes by Model Armor, transcribed by Cloud
Vision, and then screened a second time as plain text before any model sees
them.

A coordinator agent triages the case and hands it to specialist reviewers.
Every determination has to quote the municipal code word for word, and a
verifier checks those quotes byte for byte against the committed corpus. If a
quote does not match, the case goes back for a critique and a retry. Either
way, the verifier's report travels with the case.

Then it stops. Only a named human, working through an IAM-gated console, can
approve, deny, issue or close a case. Issuing writes a one-time row in
`approvals/`, and the single-writer case store checks for that row inside the
transition itself. A permit cannot exist without a record of who signed it.

Measured on the deployed stack: a demo application with a floor plan attached
went from `case.received` to the human gate in about **62 seconds**, with a
verifier-passed recommendation citing §17.44.100, and the attachment OCR'd and
screened on the way through.

When something hostile arrives, the system deals with it on its own. In one
drill, an email carried override instructions that existed only as pixels
inside a screenshot. We byte-verified that the text was nowhere in the file.
Cloud Vision transcribed it, the plain-text screen caught it at HIGH
confidence, and the case went from RECEIVED to QUARANTINED with the bytes
locked in a private bucket, an incident opened, and one trace id linking all
three audit events. **Zero engine calls. Zero human involvement.** That case
(`case-1216f7712d35`) and its incident metadata are on the live console right
now.

## How we built it

All of it runs on Google Cloud, and the infrastructure is Terraform-only. No
console click-ops.

- **Vertex AI Agent Engine + ADK.** Four deployed agents (`caseflow` for
  coordinator, intake and zoning, plus `safety`, `letters` and `treepres`),
  each running as its own least-privilege service account with a custom role.
  Agent-to-agent access is per-resource IAM, and a deliberate-deny test
  produced an audited 403. `treepres` was registered and human-approved
  mid-run through the registry, with nothing redeployed.
- **Gemini** (`gemini-3.5-flash`) for coordination, intake and review.
- **Gemma 4 (26B, Vertex AI managed API)** as the decidability judge inside the
  verification layer. It answers one question: is this request for more
  information even warranted? We used a different model family on purpose,
  because the Gemini Flash entailment judge had measurably co-signed that exact
  failure class. Gemma is hardened against two things we measured live on that
  surface: it is not deterministic at temperature 0 (five identical calls
  flipped the verdict once in five), and it accepts `response_schema` without
  enforcing it. So the check only fires when two independent calls agree and
  the quote it produces verifies byte for byte against the application.
- **Cloud Vision** for OCR at intake. A transcription engine, not a chat model,
  so pixels cannot give it instructions.
- **Model Armor** at four screening points (`inbound_content`,
  `worker_output`, `letter_draft`, `memory_write`), all four live-measured.
- **Firestore** as the single-writer case store, the write-once inbox queue,
  write-once approvals, incidents and the agent registry. **Pub/Sub** for
  events (12 topics, one per event type), **Cloud Tasks** for long timers,
  **Cloud Run** for the registry and both console services, **Cloud Build** for
  images, **BigQuery** for the audit log sink, **Cloud Trace** for OTel spans.
- **Vertex AI RAG** over one chapter of a real public municipal code (City of
  Monrovia, CA, Title 17 Ch. 17.44 "Special Uses", 37 sections, attributed in
  `data/CORPUS_SOURCE.md`), and **Vertex AI Memory Bank** for recall across
  multi-week gaps.
- Python 3.12, a `uv` workspace, `ruff` and strict `mypy`, with Pydantic
  contracts as the single source of truth for every schema. Current gate: 331
  passed, 14 skipped, 90.23% coverage.

The whole build ran under a written working agreement: phase gates, ask-first
rules for anything touching IAM, spend or guardrails, and an evidence log that
records what was measured rather than what we hoped for. Two Cloud Run consoles
enforce the split. The public reader's service account holds exactly one Google
Cloud role (`roles/datastore.viewer`), so it cannot write, cannot spend, cannot
publish events and cannot read a quarantined document, no matter what its code
does. The clerk console, where approvals actually happen, is IAM-gated to one
named person.

## Challenges we ran into

**We shipped a failing grade on our own public page, for weeks.** The
decision-accuracy gate is 85%. Five full runs measured between 65% and 80%. We
never lowered the threshold, and `/evals` renders the report unedited whatever
the gate says, so the red number was public the entire build.

**The run-to-run wobble was real, and it was ours.** Identical facts produced
`deny` on one run and `request_info` on the next, at temperature 0, on the same
config. Both readings are defensible under the statute. We characterised the
variance instead of averaging it away, and every claim in this project carries
its spread.

**We measured our way out instead of guessing.** Two levers were run as real
experiments, with thresholds pinned before the data existed:

- **Gemini 2.5 Pro at the decision step.** A statute-level study predicted two
  of five misses were fixable by a stronger model. Both of them converted, and
  Pro still scored the same 15/20. It regressed a case that had been solid,
  failed another on output-schema compliance, dropped groundedness below its
  gate, and ran about 50% slower. Measured conclusion: model tier is not the
  constraint.
- **"The model extracts, code decides"** (ADR-008). A full rules engine over 14
  corpus sections and 82 elements, passing 20/20 offline. Live it measured
  11/20 and was reverted under the threshold we had pinned before the run.
  Deterministic composition turned out to be necessary but not sufficient. The
  real frontier is which sections extraction engages in the first place.

Both artifacts are archived in `evals/archive/`. Neither is a shipped claim.

**The defect hunt on freeze eve.** The night before freeze, artifact-level
failure recording finally exposed a real bug instead of a model wobble.
Intake's instruction still listed exactly one permit type from an early phase,
so anything off that list missed the config lookup, the verifier's legality
step failed every possible outcome, and its misleading critique corrupted
retries. It measurably flipped one correct finding into a wrong one. We fixed
it, and the 12-case CI smoke subset then measured 12/12 three consecutive
times. The 8 harder held-out cases measured 3/8 in the same run, which put the
remaining failure exactly where it belongs: model decision behaviour on hard
cases, split between over-asking and over-deciding, with every miss named by id
in the report.

**The verifier result we did not want.** Our retry loop cost 2.5 times the
tokens and corrected zero of the seven findings it retried. We published that.
What the verifier actually buys, measured, is citation fidelity: groundedness
first-pass 100% versus 91.7% with it off, citation precision 91.7% versus
87.5%. That is the claim we make for it, not decision correction.

## Accomplishments we're proud of

Every number below is scoped to the run that produced it.

- **About 62 seconds**, measured on the deployed stack, from `case.received` to
  a verifier-passed determination citing §17.44.100 at the human gate, with a
  floor-plan attachment OCR'd and screened on the way.
- **A hostile screenshot contained autonomously.** Pixels transcribed, matched,
  case quarantined byte-identical, incident raised, one trace id across all
  three audit events. Zero engine calls, zero human involvement.
- **Groundedness first-pass 100%** on the shipped full run (gate is 95%), and a
  canary leak rate of 0.00% in every eval run and both ablation arms.
- **9 of 9 drill fixtures blocked** with screening on, none of them reaching a
  model, against 7 of the 8 that scored steering the fleet to approve with
  screening off. Scope, stated plainly: text carriers only (the 6 PDF-carrier
  fixtures have no unscreened ingestion path), and there is no no-injection
  control arm, so the OFF number is a strong indicator rather than proof.
- **CI smoke gate 12/12, three consecutive runs** after the freeze-eve fix.
- **75% (15 of 20) full-set accuracy, shipping red** on a public page with
  every miss named. The threshold was never touched.
- **Per-agent least-privilege IAM**, with a deliberate-deny test backed by an
  audit entry.
- **Runtime hot-add.** A new specialist registered and human-approved mid-run,
  routed to by the coordinator, with nothing redeployed.
- **A 12-day time-warp resume** through Memory Bank, measured at 199 seconds
  with `CLOCK_MULTIPLIER=20000`, including a control probe showing the case
  cannot complete without the recalled facts.
- **A permit that cannot exist without a name on it**, enforced by a write-once
  approvals row checked inside the store's transition guard.

## What we learned

**Model tier was not the constraint, and neither was determinism on its own.**
We measured both, and both came back no. That is more useful than a win would
have been, and we only have it because the thresholds were pinned before the
runs.

**A gate that never fires still has to be described honestly.** Our Gemma
decidability judge fired zero times in its one full-run measurement. It ships
as conservative defense-in-depth, and we say exactly that rather than implying
it carried the result.

**Instrumentation beats intuition.** Weeks of "the model is being weird"
dissolved the moment artifact-level failure recording made one case's failure
readable. The bug was a stale list in a prompt.

**Publishing the red number is what got it fixed.** Leaving the failing gate on
a public page is uncomfortable, and it is also the thing that forced the
root-cause hunt. A project that hides its failing number never gets to fix it.

## What's next

- **Extraction scoping** (ADR-008). The live code-decides run failed by pulling
  in sections that did not apply, not by composing them wrongly. Section-level
  applicability is the named next problem, and the measurement plan is already
  written down.
- Close the remaining OCR blind spot: raster text past a PDF's fifth page.
- Add a no-injection control arm so the screening ablation becomes proof rather
  than an indicator.
- Scale work that was deliberately deferred, not designed away: indexed limit
  queries and cursor pagination on the console queue, and parallel Cloud Tasks
  consumers to replace the single serial watcher. The human gate stays the
  throughput ceiling. That is the product, not a bug.
- Re-verify clean-project spin-up end to end. It is assembled from a verified
  build history but has not been re-run from scratch, and the README says so.

## Try it

**Public console (read-only, no login):**
https://civicnexus-console-wrhx6s33dq-uc.a.run.app

Nothing on it is staged. You can click:

- the **live case queue**, which updates itself as the fleet works;
- full **case dossiers**, with determinations, verbatim code citations, and the
  verifier's report, pass or fail;
- the **incident view** (metadata only, since quarantined bytes are never
  served), including `case-1216f7712d35`, the pixel-only hostile screenshot the
  system contained by itself;
- **`/evals`**, which renders our eval report unedited whatever its gate says.
  You will land on a red 75% with every failing case named;
- a **closed case**, still browsable, whose page explains the write-once
  `approvals/` row that lives in Firestore as durable evidence of the human
  clerk walk. Stated precisely: the console explains that row rather than
  rendering its contents, because no reader route serves approvals data.

The reader's service account holds a single role (`roles/datastore.viewer`), so
it cannot write, spend, publish, or read a quarantined document.

The **clerk console**, where approvals actually happen, is IAM-gated to one
named human. Judge access is offered on request, granted by adding your Google
identity as an invoker on that service rather than by sharing credentials. The
public page renders the same approval-gate UI with the controls disabled and
the IAM reason stated.

All data on the site is synthetic (faker, fixed seeds). Strings like `CANARY-*`
are deliberately planted leak detectors, not mistakes, and every page footer
explains this.

**Repo:** https://github.com/Danishlynx/CivicNexus
The README carries the architecture diagram, the full results table, a
failure-modes section, the AI-assistance and pre-existing-code disclosure,
corpus attribution, and `THIRD_PARTY.md`.

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

CivicNexus was built under a written working agreement: phase gates with human
review, ask-first rules for IAM, spend and guardrail changes, and a
truthfulness-first evidence log. Every architecture decision is recorded as an
ADR, every infrastructure apply was authorized, and the clerk approvals were
performed by the named human operator. No pre-existing code beyond the
open-source dependencies listed in `THIRD_PARTY.md`. The municipal code corpus
is one chapter of a real public code (City of Monrovia, CA), retrieved once by
hand and attributed in `data/CORPUS_SOURCE.md`. No scraper ships with the repo,
and no affiliation or endorsement is implied. All application data is
synthetic. The adversarial fixtures (`adv-001` through `adv-025`) are synthetic
screening-drill inputs that exist solely to validate CivicNexus's own
guardrails. They target nothing external and never leave the drill path.
