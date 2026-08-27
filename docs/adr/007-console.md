# ADR-007: Phase 6 console — one FastAPI service, two exposures, real approvals

- **Status:** **RATIFIED 2026-08-27** — the human approved asks A1–A10 as scoped
  (structured ratification ask, this date): A1–A5 IAM/exposure/infra as named,
  A6 guardrail strengthening, A7 spend OK (one run, quota-quiet window per the
  runbook), A8 image-var defaults, A9 redactor-not-built deviation, A10 gate
  scope ruling. The D13 public-exposure condition was ratified earlier the same
  day. Build order §5 is now unblocked from step 1.
- **Date:** 2026-08-27
- **Deciders:** human + build agent
- **Supersedes nothing. Amends:** ARCHITECTURE §3.1 (component inventory),
  §6.2/§6.4 (approval-token minting), §11 Phase 6 scope. Deltas listed in §7;
  the §3.1/§6.2 conflict is filed as **B-015** per CLAUDE.md rule "if this file
  and ARCHITECTURE.md ever conflict, ARCHITECTURE.md wins and you flag it".

---

## 1. Context

### 1.1 The schedule is the dominant constraint

Today is **2026-08-27**. Feature freeze is **2026-08-29**. Internal submit Aug 30;
hard deadline Aug 31, 5:00 PM PT. Phase 7 (full eval run, README verified from a
clean project, diagram, video from `docs/shotlist.md` — *which does not exist* —
blog, social, Devpost) happens **after** this, with the same human who must also
record the video.

Phase 6 therefore gets **approximately one working day of one agent**. Every
decision below is made under that constraint. A smaller console that ships,
deploys, and demos beats a larger one that is half-built at freeze. Where the
spec asks for more than a day of work, this ADR cuts it and records the cut.

### 1.2 What the spec asks for

ARCHITECTURE §11 Phase 6: *"Approval gates UI, activity feed, incident view;
redactor in the write path; managed-gateway adapter if access granted. Feature
freeze. Exit: clerk can run a full case from the UI alone."*

§3.1 names two services that do not exist:

| Component | Runtime | Responsibility |
|---|---|---|
| `console` | Next.js on Cloud Run | Clerk UI: case queue, activity feed, approval gates, incident view, eval dashboard link |
| `api` | FastAPI on Cloud Run | REST for console; simulated inbox webhook; signed GCS upload URLs; mints approval tokens |

§11 scope-cut order (cut top-first, never cut evals or the video):
**managed-gateway adapter → letters-quality rubric → console polish → safety agent.**

### 1.3 What is already true (verified this session, not recalled)

**B-007 is resolved.** Cloud Run edge routing works. Live check:
`gcloud run services list --region us-central1` returns exactly one service,
`civicnexus-registry` at `https://civicnexus-registry-wrhx6s33dq-uc.a.run.app`,
revision `civicnexus-registry-00001-z6m`. A public Cloud Run console is viable.

**Public exposure is legally deployable.** Verified live:
`gcloud resource-manager org-policies describe iam.allowedPolicyMemberDomains
--effective --project=civicnexus-hack26` → `listPolicy: allValues: ALLOW`.
There is no `allUsers` binding anywhere in the project today
(`infra/terraform/registry_service.tf:103` states this explicitly). The console
would be the first.

**A hosted URL is a mandatory Devpost field** and must stay live through judging
(to Oct 1). `docs/BACKLOG.md` item 1 raises the sharper version: private hosted
projects must ship judge credentials — *"IAM-only access would fail the testing
clause."* The console is a **compliance artifact**, not only a UI.

**Firestore already holds a demo-ready dataset** (read live today):

| collection | count | detail |
|---|---|---|
| `cases` | 7 | PENDING_HUMAN ×3, IN_REVIEW ×2, TRIAGED ×1, QUARANTINED ×1 |
| `incidents` | 1 | `inc-a765e8bf34eb`, `armor_screening`, OPEN, `inbound_content`, case `case-c50219ca5166` |
| `registry_agents` | 0 | drill cleanup emptied it; hot-add starts from empty |
| `approvals` | **0** | *no writer exists* |
| `event_dedup` | 5 | |

Best demo case: **`case-5ea037e64ef8`** — PENDING_HUMAN, garage_conversion,
1 determination, 1 timer. The console has real content on first load with **zero
engine calls**, so judge clicks cost ≈ $0.

**The case document is the whole case.** `CaseStore.create_case` writes
`case.model_dump(mode="json")`, so one Firestore read yields state,
`determinations[]` (each with `citations[{chunk_id, quote}]`, `rationale`,
`confidence`, `verifier_report`), `budget`, `timers[]`, `trace_id`. A case detail
view needs **no joins**. `determinations/` never became its own collection
despite §3.2 — `add_determination` uses `firestore.ArrayUnion` onto the case doc.

**What is missing is every plural.** `CaseStore` exposes exactly `create_case`,
`get_case`, `transition`, `add_determination`, `add_timer`, `record_event_once`,
`_emit` — **no list method**. `IncidentStore` is `record` / `get` / `resolve` —
**no list method**. There is no `google_firestore_index` resource in
`infra/terraform/`, so a `where(state) + order_by(updated_at)` query would need
an index that does not exist.

**`approvals/` and `SAFE_MODE` are prose.** Verified:
`grep -rn "approvals" --include=*.py --include=*.tf --include=*.yaml libs agents
services scripts evals infra` returns **only docstrings and one error string**.
`grep -rni "safe_mode"` over the same tree returns **zero hits**. The §4 guard is
literally `if target in _APPROVAL_REQUIRED_TARGETS and not approval_id:` — any
non-empty string passes. §6.2's *"mints approval tokens"* has no implementation.

**The guard geometry, from code:**
`HUMAN_ONLY_SOURCES = {PENDING_HUMAN, QUARANTINED}` (`case.py:64`);
`_APPROVAL_REQUIRED_TARGETS = {ISSUED, DENIED}` (`case_store.py:30`). So:
`PENDING_HUMAN → APPROVED` needs `human_actor=True` only; `→ DENIED` also needs
an `approval_id`; `APPROVED → ISSUED` needs an `approval_id` and **not** a human
flag (`APPROVED ∉ HUMAN_ONLY_SOURCES`). **Consequence: ISSUED and DENIED are
currently unreachable from any UI without fabricating a string, which would be a
guardrail bypass (prime directive 4).**

**`Actor` has no human field.** `Actor(agent_id, agent_version)`, `extra="forbid"`
(`events.py:34`). A named human cannot ride the event envelope's actor; it must go
in `payload` and in the `approvals/` row.

**Publishing blocks.** `EventPublisher.publish` ends in
`future.result(timeout=10.0)` — *"an event that cannot be published is a failed
side effect the caller must see, never a silent drop."* `CaseStore.transition`
always calls `_emit`. **Therefore a console approve click without
`roles/pubsub.publisher` hangs 10 seconds and then hard-fails.** Only
`sa-timers` holds that role today (`infra/terraform/timers.tf:31,70`). This is
the single most easily-missed IAM dependency in Phase 6.

**The deploy pattern is proven and Python-only.** `services/registry/` is four
files (`pyproject.toml`, 16-line `Dockerfile` with repo-root build context and
`uv sync --frozen --no-dev --package`, 14-line `cloudbuild.image.yaml`,
118-line `registry_service.tf` of which ~35 lines are the reusable core).
Verified: there is **no `package.json` anywhere** in the repo
(`find . -name package.json -not -path "*/.venv/*"` → empty).
`jinja2` is **not** in `uv.lock` (`grep -c 'name = "jinja2"' uv.lock` → 0) but
`starlette 1.6.0` ships `Jinja2Templates` and `fastapi 0.141.1` is installed.

**`services/` is outside both quality gates.** `pyproject.toml:114`
`testpaths = ["libs", "agents", "evals"]`; `Makefile:31` runs
`mypy libs agents scripts evals`. Verified today that adding it is free:
`uv run mypy services` → *Success, 4 source files*; `uv run pytest services` →
*6 passed, 6 skipped*. Coverage is `--cov=civicnexus --cov-fail-under=80`, and
`registry` is deliberately a top-level package outside that namespace.

**Terraform footgun (B-010).** `registry_service.tf:34` is
`count = var.registry_image == "" ? 0 : 1` with `default = ""`. An apply without
`-var registry_image=…` plans the **live registry as destroyed**. Applies are
human-run (the agent's auto-mode classifier blocks `terraform apply`). A second
image variable doubles this trap.

**ADR-005 contains a claim that is false.** It states the §7 eval preflight
*"now asserts"* an empty registry. Verified:
`grep -n "registry\|APPROVED\|preflight" evals/runner.py` → **no hits**. The
invariant currently holds only because `registry_agents` happens to be empty —
which a console approval screen or one hot-add rehearsal would end.

---

## 2. Decisions

### D1 — Stack: one FastAPI package, server-rendered HTML with Jinja2. Next.js is rejected.

`services/console/`, top-level Python package `console`, mirroring
`services/registry/` file-for-file so nothing new is learned on freeze day.
Templates via `starlette.templating.Jinja2Templates`; one `uv add jinja2` (pure
Python, pulls `markupsafe`).

**Why.** Next.js means a new language runtime, a new lockfile, a multi-stage
Dockerfile, a second image, CORS, and a hand-written TypeScript mirror of
`libs/contracts` — measured at 14–18h against 6–8h for the FastAPI path, with a
**cliff-edge** failure mode (nothing demoable until both services deploy *and*
CORS works). The FastAPI path **degrades page by page**: queue done, incidents
missing is still a shippable console.

**Why Jinja2 rather than f-string HTML.** Autoescaping is a security property
here, not a nicety. The public page renders applicant-controlled strings and, on
the incident view, **drill-fixture text engineered to contain instructions**. Any
hand-rolled interpolation is an XSS hole on a URL that stays live for five weeks.
One dependency buys contextual escaping by default.

**What it gives up.** The literal §3.1 runtime. Client-side interactivity: plain
HTML forms and full page reloads, no HTMX, no bundler. (A POST that reloads
showing the state change is also *more* legible on video than a swapped div.)

### D2 — One image, **two** Cloud Run services: a public reader and an IAM-gated clerk.

`CONSOLE_MODE` env var (`reader` | `clerk`), **defaulting to `reader`** so a
misconfiguration fails closed.

- **`civicnexus-console`** — public (`allUsers` → `roles/run.invoker`), runs as
  **`sa-console-reader`** holding **`roles/datastore.viewer` only**. Queue, case
  detail, incident view, eval report, JSON read API. Write routes are **not
  mounted**, and the reader constructs a refusing publisher rather than a real
  one. It cannot write **because IAM refuses**, not because the code declines.
- **`civicnexus-console-clerk`** — private (`user:danishlynx@gmail.com` +
  the verify-phase-6 principal), runs as **`sa-console-clerk`** holding
  `roles/datastore.user` + `roles/pubsub.publisher`. This is the instance in the
  video.

**Why two, when the research recommended one.** The one-service argument was
costed as "each new Cloud Run service costs another human-gated `terraform
apply` round-trip." **That is wrong for this case and I am correcting it:** two
services built from the *same* image are two resource blocks in *one* `.tf` file
applied in *one* apply. The marginal cost is ~30 minutes (one extra SA, one extra
service block, four lines of router gating), not a round-trip.

The marginal *risk* of the one-service alternative is not marginal. A public
console whose write path is guarded only by a shared password published in the
Devpost testing instructions means **anyone who reads the Devpost page can mutate
the exact case state the video depicts**, for five weeks. `docs/BACKLOG.md`
item 2 records that *"must function consistently… as depicted in the video"* is a
**compliance clause**. A visitor driving `case-5ea037e64ef8` to CLOSED breaks it.
Separately, copying the registry's `caller_identity` — which decodes a JWT
payload **without verifying the signature**, correct only because Cloud Run
verified it first — onto a public service would let an anonymous caller POST
`{"actor": "clerk@city.test", "human_actor": true}` and **manufacture a false
audit row naming a human who did not act**. That is a prime-directive-1 failure,
not merely a security one.

**What it gives up.** Judges reading the public URL **cannot click approve**.
`docs/BACKLOG.md` item 1 explicitly sanctions this shape ("public read-only
console (own service; registry stays non-public)"). Mitigations, both cheap:
(a) the public case page renders the approval-gate UI with controls **disabled**
and a banner naming the IAM reason; (b) after the video the demo cases sit in
ISSUED/CLOSED with their `approvals/` rows visible, so a judge sees the
*evidence* of a full clerk walk even without re-running it. Clerk credentials are
offered in the submission testing instructions on request.

**Do not copy `caller_identity` into the reader.** On the clerk service, keep it
— there the platform really did verify the token.

### D3 — Implement `ApprovalStore` for real. It is on the critical path, not a nicety.

New `libs/tools/src/civicnexus/tools/approvals.py`, mirroring `IncidentStore`
exactly: Firestore `create` (loud on duplicates), one `audit: true` log line.
Row: `{approval_id, case_id, action, target_state, approver, approval_token
(secrets.token_urlsafe), traceparent, created_at}`.

**Why it is MUST, not SHOULD.** The exit criterion requires reaching ISSUED.
ISSUED requires a truthy `approval_id`. `approvals/` is empty and has no writer.
Without this, a UI can only fabricate a string — a guardrail bypass. ~45 minutes
converts the project's most-quoted governance claim from prose into a row a judge
can read.

**And make the guard real.** `CaseStore.__init__` takes a new **optional**
`approvals: ApprovalStore | None = None`. When present, `transition` into
`ISSUED`/`DENIED` verifies the row **exists, names this `case_id`, and names this
target action** — inside the same guard path, not in the caller. When absent
(every existing test and script), behaviour is **byte-identical to today**. This
is a strict strengthening with zero regression risk to `make verify-phase-5`
(which chains `make test`), and it follows the constructor-injection shape
already used for `db` and `publisher`.

Verification must live in `CaseStore`, never in the console handler — a check the
caller performs is a check the caller can skip, which is precisely what the
single-writer architecture exists to prevent.

**Do NOT build token *consumption* plumbing.** There is no side-effect tool to
consume a token: the letters agent stages drafts only and has no send path. Say
that in the README instead of building a verifier for a caller that does not exist.

### D4 — `SAFE_MODE` is scoped out, explicitly and by name.

No fleet-wide `SAFE_MODE` flag. It is specified as a kill switch over side-effect
tools; those tools do not exist. **A flag that gates nothing is worse than no
flag — it invites a README claim that cannot be defended.**

The console's read-only exposure is **`CONSOLE_MODE=reader`**, deliberately *not*
called SAFE_MODE, so no reader mistakes it for the §11 / Appendix-A flag.
`docs/BACKLOG.md` item 1's intent (judge-accessible read-only public console) is
satisfied; the spec's `SAFE_MODE` is recorded as **not implemented** with the
property it protected named as enforced structurally instead (D2's IAM split;
no send path in the codebase).

### D5 — The MUST-have surface: five screens, one action endpoint, three JSON routes.

| Route | Content |
|---|---|
| `GET /` | **Queue.** case_id, permit_type, applicant, state badge, updated_at, determination count. Sorted **in Python** (no composite index exists). Must tolerate per-doc validation failure — `Case` is `frozen=True, extra="forbid"`, so one stray field otherwise 500s the whole queue. |
| `GET /cases/{id}` | **Detail.** Determination cards (agent@version, outcome, confidence, rationale, each `chunk_id` + **verbatim quote**), the **verifier-report panel** (the §7.3 headline, live on `case-5ea037e64ef8`), budget, timers, docs, `trace_id` → Cloud Trace deep link (§8; verify the current console URL shape at build time per prime directive 10), and a **derived activity feed**. |
| `POST /cases/{id}/action` | **Approval gates.** Clerk mode only. |
| `GET /incidents`, `GET /incidents/{id}` | **Incident view** — metadata only (D8). Phase 5's gate item, paid off. |
| `GET /evals` | Renders `docs/eval-report.md` **unedited**, failing gate visible: *"Gates: FAIL — decision_accuracy 0.750 < 0.85"*. This is B-006 honesty on the record. **No Looker Studio dashboard was ever built — do not imply one exists.** |
| `GET /healthz`, `GET /api/cases`, `GET /api/incidents` | The §6.2 `api` JSON surface, same process. |

Two rules on the buttons:

1. **Derive them from `can_transition()` and `is_human_only()`, never hardcode.**
   Then the UI provably matches the contract. `TRIAGED` and `IN_REVIEW` have no
   legal human exit — the page says *"no clerk action in this state; the fleet
   owns this case"* rather than rendering dead buttons.
2. **The activity feed is derived, and labelled as derived.** It is built from
   `created_at`, `updated_at`, `state`, `determinations[]`, `timers[]`, and this
   case's incidents. It is **not** a replay of the §5 event stream, because that
   stream has nowhere to be read from: the `case.*` / `review.*` / `action.*`
   topics have **zero subscribers** (the only subscriptions in the repo are
   `timer-fired-*` and `incident-raised-demo`), so messages are discarded at
   publish; and the BigQuery `audit.events` sink only sees processes whose stdout
   Cloud Logging ingests, while every case to date was driven by **local**
   scripts. Building a real global feed means adding a persistent append inside
   `CaseStore._emit` — the audited single-writer hot path — for a cosmetic gain
   on freeze day. Cut. Say "derived from the case record" in the UI.

*(Worth noting and verifying, not claiming: the console runs on Cloud Run, so its
own clerk actions will produce the project's **first real** `audit.events` rows.
Link to BigQuery only after seeing rows.)*

Plus one MUST-have footer line on every page: **"All data synthetic (fixed faker
seeds). `CANARY-*` strings are planted leak detectors (§9.2)."** The live
applicant fields contain `CANARY-ROSA-NAME-2b8e` and
`CANARY-ROSA-EMAIL-7f3a` verbatim; unexplained on a public page they look like a
mistake, explained they are a governance talking point.

### D13 — Public-exposure hardening: what an anonymous visitor can and cannot do

**Human condition, ratified 2026-08-27: "make sure no one can abuse GCP from the
public page."** This decision is the answer, written as enforceable properties
rather than assurances. Each row names the mechanism that makes it true and how
it is checked.

The governing principle: **the public service is bounded by IAM, not by code
politeness.** A code bug must not be able to widen the blast radius, so every
capability the reader does not need is a permission it does not hold.

| Abuse vector | Why it cannot happen | How it is enforced / checked |
|---|---|---|
| **Run up the AI bill** (the expensive one) | `sa-console-reader` holds `roles/datastore.viewer` and NOTHING else. It has no `aiplatform` permission, so a model or engine call returns 403 even if code attempted one. There is also no call site: no console route calls `query_json`, `verify_finding`, or an agent engine. | IAM grant list (A1) + a grep test over console source for `vertexai`, `aiplatform`, `agent_engines`, `query_json`, `verify_finding` |
| **Write or corrupt case data** | `datastore.viewer` is read-only. Write routes are not mounted when `CONSOLE_MODE=reader`, and the reader constructs a refusing publisher rather than a real one. | IAM + route-mounting test + the D7 grep test for Firestore mutation calls |
| **Forge an audit entry / fake a human approval** | The reader cannot write, so it cannot create an approvals row or a case transition. `caller_identity`-style unverified JWT decoding is explicitly NOT copied onto the public service (D2). | IAM + code review; the reader has no identity-trusting path at all |
| **Read the quarantined attack documents** | The reader SA holds no Cloud Storage permission whatsoever, and no route serves object bytes. The incident view shows metadata only (D8). | IAM + no storage client is constructed in reader mode |
| **Publish events / inject into the bus** | No `roles/pubsub.publisher` on the reader SA. Its publisher is a stub that raises. | IAM + unit test that the reader publisher refuses |
| **Run up Cloud Run cost by hammering the URL** | `max_instance_count` is capped on the public service, so concurrent load is bounded rather than autoscaling into a bill. Idle cost stays ~$0 at `min_instances=0`. | Terraform `scaling.max_instance_count`, mirroring `registry_service.tf` |
| **XSS via displayed content** | Every page renders through Jinja2 with autoescaping ON. This is not cosmetic: the incident view displays drill-fixture text that is *engineered to contain instructions*, and the applicant fields are attacker-influenceable by construction. | Jinja2 default autoescape (a stated reason for choosing it over f-string HTML in D1) |
| **Reach the private clerk service** | It is a separate Cloud Run service with no `allUsers` binding — invoker is the named human plus the verify principal. | IAM (A4 binds `allUsers` to the READER only) |
| **Reach the registry or any other service** | Unchanged: the registry stays private. The console reads `registry_agents` through Firestore, never by calling the registry service. | Existing IAM; no HTTP client to internal services |
| **Harvest personal data** | There is none. All data is synthetic under fixed faker seeds, and every page carries a footer saying so and explaining the `CANARY-*` leak-detector strings. | Fixture rules (§9.2), enforced by existing dataset tests |

**The one-sentence version for the README:** *the public console holds a single
Google Cloud permission — read Firestore — so it cannot spend money, cannot
write, cannot publish, and cannot read a quarantined document, regardless of what
its code does.*

**Residual risks, stated rather than implied away:**

* An anonymous visitor CAN read every synthetic case, determination and incident.
  That is intended — it is the demo — and the data is synthetic by construction.
* Cloud Run's per-request cost is not zero. `max_instance_count` bounds the
  worst case rather than eliminating it; a sustained flood would still register
  on the bill. The existing budget alerts at $50/$100/$140 remain the backstop,
  and B-012's standing rule applies: an alert is investigated, not absorbed.
* This posture is only true once the IAM grants are applied EXACTLY as scoped. A
  broader grant to the reader SA (for convenience, later) silently removes the
  guarantee, so the grant list is pinned here and the verifier re-checks it.

**`verify_phase6` asserts this posture**, so it cannot rot: it checks the reader
service is reachable anonymously, that a write attempt through the public
service fails, and that the reader SA's role list is exactly
`[roles/datastore.viewer]`.

### D6 — "A full case from the UI alone" means `PENDING_HUMAN → APPROVED → ISSUED → CLOSED`. Intake is not in scope.

The spec settles the ambiguity: §3.1 lists the console's responsibilities as
*"case queue, activity feed, approval gates, incident view, eval dashboard link"*
— **intake is not among them**; it sits in `api` as a *webhook* (by definition
not a UI action) and signed upload URLs. §1 non-goals cap user management at
*"a single demo clerk login."* PRODUCT §3: *"Clerk as judge: human touches only
where judgment matters."* And all three §12 demo moments are script-driven — the
video shows a continuous run of the *scripts*, then the console. The UI is not
the demo driver.

**Ruling, to be stated in PROGRESS and the README:** the case *enters* via the
existing applicant path; the **clerk** completes it — PENDING_HUMAN → APPROVED →
ISSUED → CLOSED, plus the QUARANTINED re-admit — with no terminal. That is "a
full case from the UI alone" for the only user the console has. UI-driven intake
is a SHOULD (§6.2's simulated inbox webhook, ~30 min) and is not the gate.

**This ruling defines the gate, so it needs human ratification (ask A10).**

### D7 — `CaseStore` remains the only writer, enforced three ways.

1. **IAM** — the public service physically cannot write (D2). Half the risk gone
   for free.
2. **In-process imports** — the console imports `CaseStore`, `IncidentStore`,
   `ApprovalStore`, `RegistryStore` directly (all workspace deps). No HTTP hop,
   no re-typed contracts, no second copy of the state machine.
3. **A grep test in the console package (~15 lines)** asserting that no
   `.update(` / `.set(` / `.create(` / `.delete(` appears on a Firestore handle
   anywhere in console source. This is the enforceable version of a claim that is
   otherwise only documentation.

The console also **never calls the registry service** — it reads
`registry_agents` through `RegistryStore` under its own SA. That removes a
`run.invoker` grant, a network hop, and — critically — the need to redeploy the
stale registry revision (`/healthz` 404s on `civicnexus-registry-00001-z6m`)
before the video. **Correcting the research here:** the "redeploy the registry
before writing any code" prerequisite applies only to a design where the console
depends on it. This design does not.

### D8 — Two hard content rules: ids-only logging, metadata-only incidents.

**Log ids only** — `case_id`, `state`, `actor`, `approval_id`, `traceparent`.
Never a case dict, never an applicant object, never a request/response body.
`libs/otel`'s `JsonFormatter` copies every `extra` verbatim to stdout and a
Terraform sink routes `audit: true` to BigQuery `audit.events` — which is exactly
where §9.2's canary-leak metric looks. One assertion in the console tests.

**The incident view renders metadata only** — `incident_id`, `kind`, `cause`,
`screening_point`, the `filter_matches` table (`pi_and_jailbreak MATCH_FOUND @
LOW_AND_ABOVE`), `status`, `actor`, `traceparent`, and `quarantine_uri` as
**inert text**. No download, no preview, no signed URL, no proxy. Serving those
bytes from a public URL would republish drill fixtures and contradict "drill
content never leaves the drill path." It is also the better demo: the point is
that the system **caught and contained** it.

### D9 — Deploy and Terraform shape.

- Package named **`console`**, top-level — **not** `civicnexus.console`. Coverage
  is `--cov=civicnexus --cov-fail-under=80`; a lightly-tested UI inside that
  namespace would drag the gate under on the last day. This mirrors `registry`.
- `Dockerfile` and `cloudbuild.image.yaml` copied from `services/registry/`
  (repo-root build context; `--package civicnexus-console`; tag `console:v0.1.0`).
- Workspace registration in **three** places: `[tool.uv.workspace] members`,
  `[tool.uv.sources]`, `[tool.mypy] mypy_path`. Then **`uv lock` in the same
  commit** — `uv lock --check` is the *first* step of `make test` and a stale lock
  has already cost this project a confusing 20 minutes once.
- **Add `services` to `testpaths` and to the Makefile's mypy args.** Verified
  green today (`mypy services` → Success, 4 files; `pytest services` → 6 passed,
  6 skipped), so this adds coverage without adding red. Otherwise the console
  ships with no type or test gate at all — exactly the quiet gap prime directive 1
  forbids.
- `infra/terraform/console_service.tf`: 2 SAs, 3 project IAM members, 2
  `google_cloud_run_v2_service`, invoker bindings. `min_instance_count = 0`,
  `max_instance_count = 2`. Reuses the existing
  `google_artifact_registry_repository.images`.
- **Give both image variables non-empty defaults** pointing at the current tags,
  so an apply with a forgotten `-var` can never plan a destroy (B-010 / the
  "3 to destroy" trap). Confirm with `terraform plan` (no `-var`) showing **no
  changes** before the human applies. This is a 2-line change that removes a
  live-service footgun the day before the video.

### D10 — Cut list, in §11's order, each recorded rather than silently undone.

| Cut | Reason |
|---|---|
| **Managed-gateway adapter** | Top of §11's cut order. No `services/gateway` exists; the gateway-scope reframe was already ratified at the Phase 3 gate; `docs/BACKLOG.md` records the managed Agent Registry API as "Not enabled", so enabling it is itself a Terraform change plus an apply. |
| **Letters-quality rubric** | Second in the cut order. |
| **Console polish** | Third in the cut order — **taken up front, deliberately**: no CSS framework, no HTMX, no JS build, no live updates (refresh-to-see-new). Better to choose this cut now than discover it at 2am on the 29th. |
| **Redactor in the write path** (§11 Phase 6, *not* in the exit sentence) | Nothing exists; `grep -rn redact` hits only `armor.py`'s response parsing and a `demo_timewarp.py` comment; `armor.tf` already records the deferral in-comment. It is a whole agent (Gemma via Vertex or Cloud DLP) plus write-path integration plus IAM. **Honest treatment (~20 min, not zero):** state in README failure-modes and PROGRESS that the dedicated redactor is NOT built, and name the *measured* compensating controls — Model Armor's `sdp` filter runs in detect mode at all four §6.3 screening points with `match_state` recorded on every incident, memory writes block on SDP matches (ADR-006 D4), canary leak rate measured **0.0%** in every eval run and both ablations, synthetic data only. **Needs a one-line human ratification (ask A9).** |
| **Signed GCS upload URLs / document viewer** | `Case.docs` is never populated by `run_case.py`; `docs-raw/` and `docs-redacted/` **do not exist** (only `agent-staging` and `docs-quarantine`). Costs new buckets + `roles/iam.serviceAccountTokenCreator` self-impersonation for `signBlob`. No judge needs it. |
| **Global `SAFE_MODE`** | D4. |
| **Real event-sourced activity feed** | D5. |
| **`REGISTRY_MODE=http` revert; registry redeploy; caseflow redeploy** | D7 removes the dependency. ADR-005's sequencing rule puts the hermetic-build parity gate before any caseflow redeploy; three days before the video is the wrong moment to rebuild the engine for a cleanliness win. **Do not touch `agents/caseflow/**`.** Record the deferral. |
| **Building letter-draft screening (point 3) into the console** | D11. |

### D11 — Close screening point 3 with a script run, not console code.

PROGRESS records point 3 (letter drafts) as *"deferred to the Phase 6 console
caller."* But the code **already exists**: `scripts/demo_injection.py`'s letters
leg screens `f"{draft.subject}\n\n{draft.body}"` at
`ScreeningPoint.LETTER_DRAFT` behind `--with-letters`. One run of
`make demo-injection DEMO_ARGS=--with-letters` closes it for one billed engine
run and **zero build hours**. Building it into the console costs half a day.
Take the run (ask A7), and record the delta plainly: point 3 was closed by the
drill harness, not by the console caller.

### D12 — Fix ADR-005's false preflight claim (~10 lines, droppable to Phase 7).

Add the missing assert to `evals/runner.py`: count APPROVED registry cards before
the first query; abort with the count if non-zero. ADR-005's HARD CONSTRAINT
rests on this preflight *"now"* asserting an empty registry, and it does not
exist. Phase 6 is what creates the risk — one hot-add rehearsal or one console
fleet action leaves a card behind and the next eval run silently measures a
different agent than the 10/12 configuration. Fixing a false claim in a ratified
ADR is a truthfulness item owed regardless of schedule.

---

## 3. Alternatives considered

**Next.js `console` + separate FastAPI `api`, exactly as §3.1/§6.2 specify.**
Killed. Zero Node toolchain exists in the repo (no `package.json` anywhere; the
`.gitignore` entries for `node_modules/` and `.next/` are speculative). It
requires a second image with a node build stage, a second lockfile, CORS, and a
hand-maintained TypeScript mirror of `libs/contracts` — 14–18h against 6–8h, with
a cliff-edge failure mode on a one-day budget, and §11 explicitly permits cutting
console polish. **This rejects the spec, so per CLAUDE.md's conflict rule it is
filed as B-015 with the ARCHITECTURE deltas in §7 below.**

**Streamlit or Gradio.** Killed by contest rules, not engineering — it is
otherwise the fastest option on the board (5–7h). The Streamlit chrome and
hamburger are unmistakable third-party branding, and `docs/BACKLOG.md`'s
video-day reminder records that the rules **disqualify** visible third-party
branding.

**Static SPA on Firebase Hosting or a GCS bucket + `api`.** Killed.
`firebasehosting.googleapis.com` is **not** in `apis.tf` — a new product plus new
Terraform. GCS-static has no HTTPS without a load balancer (~$18/month standing),
which blows the cost guard. Same cliff-edge failure mode as Next.js.

**One service, public, with writes behind a shared demo password.** Killed by
D2's reasoning: anyone reading the published Devpost credentials could mutate the
exact state the video depicts, for five weeks, breaching the "functions
consistently as depicted in the video" compliance clause.

**Console calls `registry` / a separate `api` over HTTP.** Killed. Adds a
`run.invoker` grant, a network hop, a second failure surface, a forced registry
redeploy, and duplicated contracts — for nothing an in-process import does not
give free, while weakening the single-writer story.

**Full approval-token verification plumbing + fleet-wide `SAFE_MODE`.** Killed.
No consumer exists — there is no send path anywhere in the codebase; the letters
agent stages `action.pending_approval` and nothing more. Building a verifier for
a caller that does not exist, or a kill switch over tools that do not exist,
produces claims that cannot be defended. D3 implements the narrow thing that
*does* have a consumer; D4 names the wide thing as not built.

**Persisting an events collection inside `CaseStore._emit` for a real activity
feed.** Killed for this phase. ~15 lines, and every existing script would emit
feed rows for free — but it modifies the audited single-writer hot path two days
before freeze for a cosmetic gain, and it is guardrail-adjacent. D5's derived
timeline is honest and free.

**HTMX or any client-side interactivity.** Killed. No bundler exists; HTMX means
vendoring a minified blob into `static/`. Full page reloads read better on video.
Revisit only if MUST lands with hours to spare.

---

## 4. The exit proof

Two halves: a green machine check and one human observation.

### `make verify-phase-6` (replaces the current `echo FAIL` stub)

`make test` (now covering `services`) **and** `uv run python scripts/verify_phase6.py`.
The script is **$0** — HTTP and Firestore only, no engine calls — and
authenticates to the private clerk service with an identity token using the
existing `fetch_id_token` pattern from `registry_toolset.py`. *(Correction,
2026-08-27 pre-apply audit: `fetch_id_token` mints SERVICE-ACCOUNT tokens,
and A4 binds the clerk invoker to the named HUMAN, so that pattern would 403
against a correct deployment. The verifier uses `gcloud auth
print-identity-token` — the caller's own user identity, same platform
verification. Recorded as a delta rather than silently deviating.)* Every
assertion:

1. `GET {PUBLIC_URL}/healthz` → **200 unauthenticated** (B-007's resolution and
   the mandatory Devpost hosted URL, proven live).
2. `POST {PUBLIC_URL}/cases/{id}/action` → **404** (write routes not mounted in
   reader mode), and the reader SA's `roles/datastore.viewer`-only binding is
   cited as Terraform-declared evidence.
3. Create throwaway fixture `case-ui-verify-<hex>` via `CaseStore`, drive
   RECEIVED → TRIAGED → IN_REVIEW → PENDING_HUMAN. *(Fixture setup is not a UI
   action; the clerk's case begins at PENDING_HUMAN — D6.)*
4. **Through the deployed clerk console's own HTTP endpoints only:** Approve →
   Issue → Close. No direct store calls in this leg.
5. Assert the case is `CLOSED`, and assert an `approvals/` row exists that names
   a **human**, the **action**, and the **target state** for the ISSUED
   transition — i.e. §4's guard is now a row, not a docstring.
6. Assert `GET {PUBLIC_URL}/` contains the case id (queue renders it).
7. Assert `GET {PUBLIC_URL}/incidents/inc-a765e8bf34eb` → 200, contains
   `pi_and_jailbreak`, and contains **no** signed URL and no quarantined bytes.
8. Second throwaway case: quarantine it, **re-admit via the clerk UI**
   (`QUARANTINED → IN_REVIEW`, human-only), close it. This is the Phase 5 gate
   item exercised end to end. *The live demo case `case-c50219ca5166` is video
   evidence and is never touched.*
9. `try/finally` delete both fixture cases and their approvals rows (the D18
   cleanup pattern from `drill_tool_poisoning`).

### The human half

The human, acting as the clerk, drives one real case in a browser from
PENDING_HUMAN to CLOSED during video rehearsal, with no terminal open — and sees
the `approvals/` row appear naming them. That is the exit sentence, observed.

---

## 5. Build order

Target ≈ 8h15 of agent time plus one human apply. Front-loaded so the video
beats exist early and so a freeze at any step still leaves something shippable.

| # | Step | Est. | Notes |
|---|---|---|---|
| 0 | This ADR committed; **B-015** filed; human ratifies asks A1–A10 | 30m | Blocking. No code before the IAM and exposure asks are answered. |
| 1 | `ApprovalStore` + optional verification hook in `CaseStore` + unit tests | 45m | Pure `libs/`. `make test` green. **Highest judge-value-per-hour item and it needs no UI to be true.** |
| 2 | `list_cases()` / `list_incidents()` + per-doc validation tolerance + tests | 30m | Sort in Python — no composite index exists. |
| 3 | `services/console/` skeleton: pyproject, Dockerfile, cloudbuild, workspace + mypy registration, `uv lock`, `services` added to `testpaths`/mypy, `make test` green. Routes `/healthz`, `/` queue, `/api/cases`; Jinja2 base template | 60m | Run `make test` immediately after the pyproject edit so a lock or gate surprise surfaces in minute one, not hour eight. |
| 4 | `gcloud builds submit`; write `console_service.tf` (2 SAs, 2 services, invoker bindings, non-empty image-var defaults); `terraform plan` with **no** `-var` shows no destroys; **human runs apply**; capture both URLs into PROGRESS | 60m + human | **⚠ POINT OF NO RETURN.** This fixes the service names and the public URL that Devpost, the README, and the video will all cite. After this, changes ship as image pushes only — never a new service name. Deploying a *skeleton* here means the first `allUsers` binding, the reader/clerk split, and the public URL are all proven before lunch. |
| 5 | `GET /cases/{id}`: determination cards, citations + verbatim quotes, verifier-report panel, budget, timers, trace deep link, derived activity feed, synthetic-data footer. Rebuild + push | 75m | The video's second beat. |
| 6 | `POST /cases/{id}/action`: buttons derived from `can_transition()`; approve / deny / request_info / issue / close / re-admit / discard, through `CaseStore` with `ApprovalStore` minting. Clerk mode only. Rebuild + push | 75m | The video's third beat and the exit criterion. **If the freeze lands here, the console is still complete enough to demo and to pass the gate.** |
| 7 | `/incidents`, `/incidents/{id}` (metadata-only) + resolve + quarantine exit; `/evals` renders `eval-report.md` unedited; `/api/incidents`. Rebuild + push | 60m | Phase 5's gate item paid off; B-006 honesty on screen. |
| 8 | `scripts/verify_phase6.py` + `make verify-phase-6`; run it green | 60m | §4. |
| 9 | PROGRESS + BLOCKERS (B-015) + README (hosted URL; replaces the "Phase 0 — not yet deployed" banner) + ARCHITECTURE deltas + redactor honesty paragraph; copy `.deploy/*_last_run.json` Phase 5 evidence into a committed `docs/evidence/`; **freeze declared** | 45m | The evidence copy is cheap insurance: `.deploy/` is gitignored and B-012's three NUL-truncation events have an open root cause. |
| 10 | `evals/runner.py` registry preflight (D12) | 15m | Droppable to Phase 7 without blocking the gate. |

**SHOULD list, only if MUST lands with hours to spare, in value order:**
corpus quote highlight (render the cited span highlighted — the single most
convincing five seconds in the UI, ~20m) → read-only fleet page over
`registry_agents` so hot-add is visible in the UI as the card flips (~30m) →
`/inbox` simulated webhook creating a case at RECEIVED (~30m).
**Not on the SHOULD list:** any "run review" button — it needs an `aiplatform`
IAM grant and would expose a billed action on a public URL through Oct 1.

**Phase 7 input noticed en route: `docs/shotlist.md` does not exist**, though §12
and CLAUDE.md both reference it. Write it at the freeze, not after.

---

## 6. Risks and asks

### Needs a human decision before step 1

| # | Ask | Role / principal / reason |
|---|---|---|
| **A1** | IAM | `roles/datastore.viewer` → `serviceAccount:sa-console-reader@civicnexus-hack26.iam.gserviceaccount.com`. **Reason:** the public console must read `cases/`, `incidents/`, `registry_agents/` and must be structurally incapable of writing. |
| **A2** | IAM | `roles/datastore.user` → `serviceAccount:sa-console-clerk@civicnexus-hack26.iam.gserviceaccount.com`. **Reason:** the clerk console writes case transitions, approvals rows, and incident resolutions through `CaseStore` / `ApprovalStore` / `IncidentStore`. |
| **A3** | IAM | `roles/pubsub.publisher` → `serviceAccount:sa-console-clerk@…`. **Reason:** `CaseStore._emit` → `EventPublisher.publish` blocks on `future.result(timeout=10.0)`; **verified in code**, so without this grant every clerk action hangs ten seconds and hard-fails. Only `sa-timers` holds this role today. Scope to the 12 event topics if project-level is unwelcome. |
| **A4** | **Public exposure** | `allUsers` → `roles/run.invoker` on **`civicnexus-console` (reader) only**. The project's **first** `allUsers` binding. **Reason:** Devpost mandates a hosted URL testable by anonymous judges through Oct 1; `docs/BACKLOG.md` item 1 records that IAM-only access would fail the testing clause. The registry and the clerk console stay private. Org policy verified permissive; the binding itself is still an untested apply. |
| **A5** | Billed infra | Two Cloud Run services, `min-instances=0`, ~$0 idle, well under the ~$10/day guard; must stay deployed through Oct 1. |
| **A6** | **Guardrail change** | Adding approvals-row verification to `CaseStore.transition` via optional injection (D3). Strengthens, never weakens; the default path is byte-identical, so `make verify-phase-5` cannot regress. Ask-first per the Working Agreement because it touches a guardrail. |
| **A7** | Spend OK | One `make demo-injection DEMO_ARGS=--with-letters` run to close screening point 3 (D11) — one billed engine run. |
| **A8** | Terraform | Set non-empty defaults on `registry_image` and the new console image var, removing B-010's "3 to destroy" trap. Touches a variable controlling a live service — confirm with `terraform plan` (no `-var`) showing **no changes** before applying. |
| **A9** | Deviation ratification | Redactor in the write path (§11 Phase 6) **not built**; compensating controls named honestly (D10). |
| **A10** | Scope ruling | "Clerk can run a full case from the UI alone" read as PENDING_HUMAN → CLOSED, intake excluded (D6). This defines the gate, so the human should ratify the reading. |

### Risks carried, with mitigations already chosen

- **Cold start on video day.** Both services are `min-instances=0`. A registry
  probe measured 0.50s then 0.42s today, but the service had been probed earlier,
  so **that is not a cold-start number and must not be quoted.** Before rehearsal,
  leave the console idle ~20 minutes and time one request. If unpleasant,
  ADR-005's costed video-day lever (`min_instances=1` for the recording day only,
  ask-first, reverted after) already exists.
- **`evals/results.json` is one stray command from being replaced.** The runner
  writes it unconditionally on any non-ablation run, and the current file *is* a
  12-case smoke artifact. **Do not run `make eval-smoke` locally during Phase 6**;
  restore from `evals/archive/results-verifier-on-20260825.json` if it happens.
- **CI runs a billed 12-case eval on every push to main.** Keep `[skip ci]` on
  every Phase 6 commit unless a run is intended and OK'd.
- **`uv lock --check` is the first step of `make test`.** Regenerate the lock in
  the same commit as the pyproject edit (step 3).
- **Coverage gate.** Package must be `console`, not `civicnexus.console` (D9).
- **`Case` is `frozen=True, extra="forbid"`.** One stray field in one document
  otherwise 500s the entire queue page. Per-doc validation tolerance is a MUST,
  not a nicety (D5).
- **Demo-state integrity.** The reader service cannot mutate anything;
  `verify_phase6` uses throwaway fixture cases with `try/finally` cleanup and
  never touches `case-5ea037e64ef8` or `case-c50219ca5166`.
- **Must-not-regress, pinned above the worklog:** do not touch or redeploy
  `agents/caseflow/**`; keep `registry_agents` at zero APPROVED cards outside a
  rehearsal (`scripts/demo_reset.py --confirm` immediately after); do not
  regenerate drill fixtures (D10 — regeneration invalidates canary-green);
  the `civicnexus-armor` template config stays frozen; the live
  `civicnexus-registry` service survives every apply (A8);
  `make verify-phase-5` must still pass, since it chains `make test`.

---

## 7. Consequences and ARCHITECTURE deltas (→ BLOCKERS **B-015**)

**Easier.** One image, one build, one apply, one language. Every page is one
Firestore read. The console imports the governance model in-process, so
`CaseStore`'s guards apply with no contract duplication and no network hop. The
`approvals/` guard becomes a row a judge can read. Public read-only exposure is
IAM-enforced, so the README gets to say *"it cannot write because IAM refuses"*
and survive a judge poking at it.

**Harder.** No rich client interactivity without a later rewrite. Judges on the
public URL read but do not click. A second Cloud Run service is one more thing to
keep alive through Oct 1.

**Now forbidden.** No direct Firestore mutation in console code (grep-tested). No
`caller_identity`-style unverified JWT decoding on the public service. No serving
quarantined bytes. No case dicts or applicant objects in log `extra`. No local
`make eval-smoke` during Phase 6. No caseflow or registry redeploy in Phase 6.

**Deltas to record against ARCHITECTURE.md:**

1. **§3.1** — the `console` (Next.js) and `api` (FastAPI) rows collapse into one:
   *`console` — FastAPI + Jinja2 on Cloud Run, deployed as two services
   (public reader / IAM-gated clerk) from one image; serves both the clerk HTML
   and the `api` JSON surface.* **No separate `api` service exists.**
2. **§6.2 / §6.4** — *"approval token minted by `api`"* → minted by
   `ApprovalStore` (`libs/tools`) and **verified inside `CaseStore`**, the single
   writer. Token *consumption* plumbing is not built: there is no send path in
   the codebase.
3. **§3.2** — `determinations/` never became its own collection; determinations
   live inside `cases/{id}` via `ArrayUnion`. Recording an existing fact, not a
   new change.
4. **§11 Phase 6** — *"redactor in the write path"* **cut** (compensating
   controls named); *"managed-gateway adapter"* **cut** (top of §11's own
   scope-cut order); *"activity feed"* delivered as a **derived per-case
   timeline**, not an event replay.
5. **§11 / Appendix A** — `SAFE_MODE` is **not implemented**. The console's
   read-only exposure is `CONSOLE_MODE=reader`, a deliberately different name.
6. **§6.2 `api` line items not built:** simulated inbox webhook (SHOULD, likely
   cut), signed GCS upload URLs (cut — `docs-raw/` and `docs-redacted/` do not
   exist).
7. **§8** — the Looker Studio dashboard was never built; `/evals` renders
   `docs/eval-report.md`. The README must not imply a dashboard exists.
8. **ADR-005 correction** — its claimed §7 eval preflight asserting an empty
   registry does not exist in `evals/runner.py`. D12 adds it.
