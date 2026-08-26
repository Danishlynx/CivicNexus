# ADR-005: Resilience architecture (pre-freeze hardening)

- **Status:** proposed — requires human ratification. Items marked **ASK-FIRST**
  need explicit per-item approval under the Working Agreement (IAM, billed
  infra, eval-harness changes, anything touching the judge).
- **Date:** 2026-08-26
- **Deciders:** proposed by Claude (build agent) from the verified flaw-map
  review (three independent code/platform/ADK research passes, 2026-08-26);
  ratification pending.
- **Relationship to ADR-004:** the ADR-004 AgentTool wiring was reverted for
  the variance measurement (tag `wiring-deterministic-v1`); the SHIP-OLD
  verdict (10/12, 9/12) fixed the **current measured configuration** as
  `sub_agents=[intake, zoning]` with `mode="single_turn"` (auto-wrapped by ADK
  2.7.1 as `_SingleTurnAgentTool`s). This ADR assumes and preserves that
  wiring byte-for-byte.

---

## HARD CONSTRAINT (governs every item below)

**The measured eval configuration must remain byte-identical on the eval
path.** "Eval path" = every LLM request the caseflow engine emits during an
eval run: coordinator + intake + zoning under single_turn sub_agents wiring,
empty registry, RAG retrieval, and the driver/verifier harness that produced
10/12 decision-accuracy and 9/12 groundedness. Additions are permitted only
where evals cannot see them; anything that could shift request bytes or
verdict semantics goes through an explicit A/B gate or is deferred.

### Exhaustive list of files this ADR changes, with eval-invisibility proof

**Engine-side (code that runs inside a deployed engine):**

| File | Change | Why evals cannot see it |
|---|---|---|
| `agents/caseflow/src/caseflow_agent/registry_toolset.py` | try/except + bounded retry inside `_consult_remote` only (§3) | With zero APPROVED cards, `get_tools()` returns `[]` (registry_toolset.py:157-169): no consult `FunctionTool` is constructed, no consult declaration enters any LLM request, and `_consult_remote` never executes. Eval runs use an empty registry by contract (§7 preflight now asserts it). Only the body of `_consult_remote` changes; toolset construction, filtering, and Firestore query bytes are untouched. |
| `agents/treepres/.../requirements.txt`, `agents/safety/.../requirements.txt`, `agents/letters/.../requirements.txt` (new) | full pinned closure (§1) | These three engines are never invoked on the eval path (evals exercise caseflow + RAG only). Their images can change freely. |
| `agents/caseflow/src/caseflow_agent/requirements.txt` | full pinned closure — **gated** (§1) | NOT eval-invisible by construction (a redeploy rebuilds the image). Gate: compile the lock, diff it against `pip freeze` probed from the currently-deployed image; deploy only if identical, else defer to Phase 6 behind an eval-smoke A/B. |
| `agents/caseflow/src/caseflow_agent/agent.py` + model construction in `coordinator.py`/`intake.py`/`zoning.py` | **NO pre-demo change.** Env-override elimination (§2) is a guarded Phase-6 candidate only. | n/a — explicitly frozen. |

**Deploy/ops-side (never executes at inference time):**

| File | Change | Why evals cannot see it |
|---|---|---|
| `scripts/deploy_agent.py` | env-manifest validation, REGISTRY_MODE pinning (§7) | Runs on the deployer machine at deploy time; validates the `.env` before `adk deploy`; produces the same baked env the measured config already has (it asserts, never mutates silently). |
| `scripts/engine_iam.py` | `raise_for_status` + timeout on getIamPolicy; propagation wait (§7) | Ops path only; evals never touch IAM. |
| `scripts/demo_hotadd.py`, `scripts/run_case.py` | reply persistence, bounded retry, preflights (§3, §6, §7) | Demo drivers are not part of the eval harness. |
| NEW `scripts/warmup.py`, NEW `scripts/demo_reset.py`, NEW `agents/*/env.manifest.json`, NEW `docs/RUNBOOK.md` | additive (§4, §7, §8) | New files; nothing on the eval path imports them. |
| `infra/terraform/*` | telemetry IAM roles, CI-trigger pause variable (§5, §6) | Infra only. |

**Harness-side (driver machine; alters the measurement instrument, so each
needs the human's evidence-precision sign-off even though engine bytes are
untouched):**

| File | Change | Why the measurement is preserved |
|---|---|---|
| `libs/tools/src/civicnexus/tools/agent_client.py` | stream-consumption watchdog (§3) | Fires only on the hang path (no event for 120s / total > 630s). Successful streams are parsed by the identical code; a run that never hangs is bit-identical in results. |
| `evals/runner.py` | registry-state preflight assert (§7); verifier call wrapped in existing `_query_with_backoff`-style retry (§3) | Preflight runs before any query and only aborts on unexpected state. Retry replays the same verifier request on 429/503 only; verdict semantics unchanged. |
| `libs/verifier/src/civicnexus/verifier/verify.py` | bounded retry around `_default_entailment` (§3) | Same judge model, same prompt bytes; retry only on transport-level 429/503. The judge's decision function is untouched. |

Everything else in the repo is unchanged by this ADR.

---

## Context

14+ recorded failures (docs/FAILURES.md, BLOCKERS.md) converge on seven
architectural gaps: non-hermetic engine builds (F13), a process-wide
`GOOGLE_CLOUD_LOCATION=global` override that poisoned SDK routing (F14), a
single shared Gemini quota pool with compounding retry layers (429 kill),
scale-to-zero engines with no warmup contract (cold-start 503s), an
uncontained consult FunctionTool that kills whole invocations, silent
state-dependence of the eval tool surface on registry contents, and no
operational runbook. Three verification passes (code audit, platform
live-docs, ADK 2.7.1 installed-source) confirmed the map, refuted the B-009
sticky-transfer framing for the current wiring, and surfaced ~20 additional
surfaces — the highest-impact ones are folded in below. Human ruling: no
demo attempts until the architecture is proper. Freeze is in 3 days.

## Decision

The eleven numbered mechanisms below, tiered **MUST-before-demo (D)** /
**MUST-before-video (V)** / **Phase-6-nice (P6)**, efforts S/M/L.

---

### §1 Hermetic builds (closes F13 class fleet-wide)

Engine images run `pip install -r requirements.txt` fresh on
`python:3.11-slim` at deploy time (ADK `cli_deploy.py:73, 1219-1224`); the
local `uv.lock` (Windows/py3.12) never constrains the image. The F13 pin fix
exists **only in caseflow's** requirements.txt; treepres and safety carry
3 top-level pins, letters has no requirements.txt at all — and the hot-add
demo deploys treepres **fresh, mid-demo, on camera**.

1. **[D, M]** Compile a full platform-correct closure:
   `uv pip compile requirements.in --python-platform linux --python-version 3.11 -o requirements.txt`
   per agent. Apply immediately to
   `agents/treepres/src/treepres_agent/requirements.txt`,
   `agents/safety/src/safety_agent/requirements.txt`, and create
   `agents/letters/src/letters_agent/requirements.txt` (all off the eval
   path). Redeploy treepres before any demo rehearsal so the on-camera deploy
   resolves a locked set.
2. **[V, S — gated]** Caseflow closure: compile the same lock, then probe the
   deployed image (`sys.version` + `importlib.metadata` dump via a one-off
   query, or `pip freeze` in a local `python:3.11-slim` container against the
   current requirements.txt) and diff. Identical → commit + redeploy + run
   the §7 preflight; any delta → defer to Phase 6 behind an eval-smoke A/B
   (**ASK-FIRST**: eval spend).
3. **[D, S]** `scripts/deploy_agent.py`: validate the freshly-written `.env`
   against the agent's `env.manifest.json` (§7) **before** invoking
   `adk deploy` — fail fast on missing PROJECT_ID (the live treepres `.env`
   is missing it today), wrong REGISTRY_MODE, or unexpected keys.

### §2 Env-override elimination or scoping (per ADK research)

Verified: the override **can** be eliminated — ADK 2.7.1
`Gemini(model=..., client_kwargs={"vertexai": True, "project": PROJECT_ID,
"location": "global"})` (google_llm.py:122-125, applied after http_options at
:370-380) pins the genai client per-model, exactly the pattern ADK's own
`ManagedAgent` uses. Platform docs additionally mark `GOOGLE_CLOUD_LOCATION`
**reserved** inside Agent Engine runtimes — our `agent.py:11` override
violates that. BUT: three code sites read `GOOGLE_GENAI_USE_ENTERPRISE` /
`GOOGLE_GENAI_USE_VERTEXAI` (capabilities, output-schema wiring, tool
declarations) and deleting/changing that one silently changes **zoning's
measured request shape**; and touching model construction is an eval-path
edit — same endpoint, but not behaviorally-invisible-by-construction.

Decision: **scope now, eliminate under guard later.**

1. **[D, S]** Scoping (zero eval-path change): keep `agent.py:11` as-is on
   the proven config; document in this ADR that every other client on the
   deployed path is env-immune, verified: RAG `agentplatform.Client`
   (explicit `RAG_LOCATION`), Firestore (explicit project), session service
   (location parsed from the `agentengine://` resource name), consult REST
   (regional URL by construction), driver `vertexai.Client` and verifier
   `genai.Client` (explicit args). Add a comment at `agent.py:11` naming F14
   and forbidding any new SDK client construction in engine code without
   explicit project/location kwargs.
2. **[P6, M — gated, ASK-FIRST]** Elimination: delete the override; construct
   pinned `Gemini(client_kwargs=...)` in `coordinator.py`, `intake.py`,
   `zoning.py` (+ treepres/safety/letters agents). Preconditions: (a) on-engine
   probe confirming the runtime provides `GOOGLE_GENAI_USE_ENTERPRISE`
   (one-line env dump query — the deploy pipeline never sets it, so model
   calls succeeding implies the runtime does; verify, don't assume); (b) one
   ratified eval-smoke A/B run holding 10/12 + 9/12 before trust. Note
   `client_kwargs` is `Field(exclude=True)` — safe for in-process
   construction, dropped by any serialization.
3. **[V, S]** Local-tooling leak: importing `caseflow_agent.agent` (pytest
   does) sets the override process-wide on the importer. Until elimination,
   the RUNBOOK (§8) forbids running any SDK-routing-sensitive script in a
   process that imported an agent module.

### §3 Per-hop containment + retry with a non-compounding budget

Governing rule: **exactly one retrying layer per failure domain.** The engine
model layer stays at 1 attempt (ADK `retry_options` deliberately NOT set —
adding it would multiply under every driver retry and is invisible to our
attempt accounting). Workflow `RetryConfig` on any node stays unset (same
reason, plus it re-bills LLM calls per retry — ASK-FIRST if ever wanted).

**Retry budget table (attempts = total including first try):**

| Layer | File | Attempts | Backoff | Triggers |
|---|---|---|---|---|
| Eval driver per query | `evals/runner.py:38-53` (existing, unchanged) | 4 | min(90, 3^n) + jitter | 429/503/RESOURCE_EXHAUSTED/UNAVAILABLE |
| Demo/one-off driver per query | `scripts/demo_hotadd.py`, `scripts/run_case.py` | 2 | 30s + jitter | connection error / 5xx **before first event only** |
| Engine model call | ADK genai (default) | 1 | — | — (unchanged) |
| Consult tool HTTP | `registry_toolset.py` `_consult_remote` | 2 | 20s + jitter | 429/503/timeout |
| Verifier entailment | `libs/verifier/.../verify.py` | 4 | same as eval driver | 429/503 |

Compounding proof: layers multiply only where nested. Eval path: driver 4 ×
model 1 = **4** model attempts per query, no consult layer exists (empty
registry). Demo path: driver 2 × consult 2 = **4** consult HTTP attempts
worst case, driver 2 × model 1 = 2 model attempts. Verifier: 4 × 1. No
logical operation can exceed **8 total attempts across all layers**, and
cumulative backoff per case is bounded by the runner's existing schedule +
the §3.4 watchdog. Retried turns re-spend the shared pool — hence the §5
scheduling windows, and pacing (`runner.py:219-220` sleep(5)) stays.

1. **[D, S]** Consult containment (`registry_toolset.py:90-128`): wrap
   `_consult_remote` body in try/except; on 429/503/timeout retry once per
   the table; on final failure **return** a structured string
   `"consult_error: <agent> unavailable (<status>) — proceed without this
   capability or report missing_capability"` instead of raising. Mechanism
   verified: `FunctionTool.run_async` does not catch (function_tool.py:303-380)
   and `functions.py:630-640` re-raises without an `on_tool_error` responder —
   today one cold-start 503 on the consult leg kills the whole invocation.
   This is the single highest-leverage fix for the observed ~50% multi-cap
   failure rate (§9). Eval-invisible per the constraint table.
   `on_tool_error_callback` (exists in 2.7.1, llm_agent.py:510) is the
   cleaner general mechanism but touches the coordinator constructor —
   rejected pre-freeze, noted for Phase 6+.
2. **[D, S — evidence-precision sign-off]** Stream watchdog
   (`libs/tools/src/civicnexus/tools/agent_client.py:46-48`):
   `list(remote.stream_query(...))` currently has **no timeout of any kind**
   (observed: 81-min hang F11, 2518s case in Run 5). Consume the iterator
   with a 120s per-event idle timeout and 630s total cap (platform hard-caps
   streams at 10 min; client cap sits just above so the server closes first).
   On trip: raise `RuntimeError("stream_timeout ...")` so existing driver
   retry/markers handle it.
3. **[D, S]** Demo driver retry + no-discard: `demo_hotadd.py` and
   `run_case.py` get the 2-attempt whole-turn retry (pre-first-event failures
   only, so no duplicated model-visible turns) and §6.2 persistence.
4. **[V, S — evidence-precision sign-off]** Verifier retry: wrap the
   entailment call (`verify.py:72-91`) in the 4-attempt backoff. Today a
   single 429 inside the verifier errors the case in `_run_one`'s catch-all
   (runner.py:149-159) and counts against **both** gated metrics — a quota
   blip can redden the gate while the fleet answered correctly. Also treat
   empty `response.text` as one retriable event before failing. Verdict
   semantics unchanged; judge model unchanged.

### §4 Warmup protocol + optional min-instances (costed)

1. **[D, S]** NEW `scripts/warmup.py`: for every engine on the run's path
   (demo: caseflow + treepres; eval: caseflow), send a trivial
   `stream_query` ("warmup ping") with the §3 demo retry budget, assert
   first event < 15s on the final attempt, print per-engine PASS/FAIL,
   bounded ≤ 5 min total. Invoked as RUNBOOK step 0 for every demo, video
   take, and eval run. Platform docs measure ~4.7s cold vs ~0.4s warm and
   explicitly endorse pre-warming with steady load.
2. **[V, S — ASK-FIRST: billed-infra decision]** min_instances for video day
   only. Verified supported end-to-end in the pinned stack:
   `client.agent_engines.update(name=<resource>, config={"min_instances": 1})`
   — no code redeploy, but it **creates a new runtime revision** (record the
   revision id in PROGRESS.md evidence; run after any eval measurement, or
   re-verify spec parity). Alternative routes: `.agent_engine_config.json`
   merged by the ADK CLI at deploy, or REST PATCH
   `spec.deployment_spec.min_instances` (same pattern `deploy_agent.py`
   already uses for the SA). Cost: during Preview, idle instance time is
   **not billed** (docs: "you won't be billed for time when an agent is
   idle") → keeping caseflow + treepres warm ≈ $0 today; worst case if
   billing changes: ~$18.3/day/engine at the default 4CPU/4Gi shape,
   ~$4.6/day at 1CPU/1Gi — under the $10/day guard only at the small shape,
   hence ASK-FIRST with these numbers. Enable the morning of the video,
   revert (`min_instances: 0`) the same day; both steps in the RUNBOOK.
3. **[P6, S]** Verify actual deployed scaling values via
   `reasoningEngines.get` — the platform default is min_instances=1, yet we
   observe cold starts; confirm what the deploy actually set before tuning.

### §5 Quota strategy

1. **[D, S — human action, reworded]** The planned model-quota increase
   request is **moot**: gemini-3.5-flash has no per-project RPM/TPM quota
   rows — it runs on Dynamic Shared Quota/PayGo, "removing the need to
   submit quota increase requests." Do not spend the human's time on a model
   QIR; the only guaranteed-capacity path is Provisioned Throughput
   (account-team, weeks — not viable before freeze). **Instead**, the
   Agent Platform API quotas ARE adjustable. Suggested filing, verbatim,
   after confirming the exact quota row in the console
   (IAM & Admin → Quotas, filter "aiplatform" + "reasoning"):
   > "Requesting an increase of the Vertex AI Agent Platform quota
   > 'ReasoningEngine StreamQuery requests per minute per region' in
   > us-central1 for project `<PROJECT_ID>` from its current value to 2×.
   > Reason: hackathon judging window Aug 29–31 runs a 4-engine agent fleet,
   > CI eval harness, and live demo concurrently; current limit produces
   > 429s during overlapping windows."
2. **[D, S]** Consumer scheduling (RUNBOOK §8): the shared pool's consumers
   are (a) CI eval-smoke — fires on **every push to main**
   (`cloudbuild.yaml:36-48`, trigger in `infra/terraform/ci.tf:11-31`),
   (b) nightly eval-full, (c) local eval runs, (d) demo/video drivers,
   (e) verifier entailment. Rule: demo/video/eval windows are exclusive —
   no pushes to main during a window. Enforcement: Terraform variable
   `ci_trigger_disabled` on the trigger (`disabled = var.ci_trigger_disabled`)
   flipped via `terraform apply` before/after the window (Terraform-only
   rule respected) **[V, S]**.
3. **[P6, S — ASK-FIRST: changes the eval judge]** Verifier pool isolation:
   flash-lite is a separate per-model DSQ pool. Introduce a dedicated
   `VERIFIER_MODEL_ID` env var in `verify.py` (today `MODEL_ID` drives both
   the engines' baked config and the driver-side judge — a shared key that
   makes any judge experiment ambiguous; split the key first, defaulting to
   current behavior). A/B guard before any switch: replay the recorded
   replies of one full 12-case run through both judges offline (verifier
   calls only, no engine spend) and require 12/12 verdict agreement.
   Activate only if verifier-side 429s persist after §3.4.
4. **[P6, S]** CI hygiene: upload `results.json` as a Cloud Build artifact
   (today a killed build discards all eval evidence), and note the runner's
   worst-case backoff can exceed the 2400s build timeout — the §3 budget
   plus §4 warmup makes that boundary explicit in the RUNBOOK.

### §6 Observability

1. **[D, S — ASK-FIRST: IAM, exact wording per the IAM evidence standard]**
   Telemetry roles, Terraform (`infra/terraform/`, engine-SA module):
   > Grant `roles/cloudtrace.agent` and `roles/monitoring.metricWriter` to
   > `sa-caseflow@<PROJECT_ID>.iam.gserviceaccount.com`,
   > `sa-treepres@...`, `sa-safety@...`, `sa-letters@...`.
   > Reason: engines are deployed with `--otel_to_cloud`
   > (GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true) but their per-agent
   > SAs lack trace/metric write, producing the observed telemetry 403s;
   > without traces, demo/video incidents cannot be triaged live.
2. **[D, S]** Driver reply persistence: `demo_hotadd.py` and `run_case.py`
   write every raw reply, full event stream, timing, and attempt count to
   `artifacts/runs/<timestamp>/<step>.json` **before** any parsing or PASS
   evaluation (today failures discard replies entirely; the PASS check
   `"tree" in after_text.lower()` is evaluated on data nobody can audit
   afterwards). The eval runner already persists via results.json —
   unchanged.
3. **[V, S]** Audit blind spot, recorded honestly: the BigQuery audit sink
   ingests only in-GCP stdout logs (`infra/terraform/audit.tf:14-24`);
   driver-side register/approve/case-transitions under human ADC produce
   **no server-side audit record** in interim firestore mode. Pre-freeze
   mitigation is disclosure (README failure-modes section + RUNBOOK note);
   the structural fix is routing mutations through the registry service once
   B-007 is resolved **[P6, M]**.

### §7 State-hygiene preflights

1. **[V, S — evidence-precision sign-off]** Eval preflight in
   `evals/runner.py`: before the first case, assert the registry has **zero
   APPROVED cards** (the tool-surface invariant the whole eval measurement
   silently rests on); abort loudly otherwise. Registry card presence
   changes the coordinator's tool surface — this turns an invisible
   state-dependence into an executable check.
2. **[D, M]** NEW `scripts/demo_reset.py`: quarantine (status → REVOKED, or
   delete) any tree-preservation cards from prior runs/rehearsals; verify
   BEFORE-state preconditions (zero APPROVED treepres cards, engines
   responsive via §4 warmup); print PASS/FAIL. Today demo re-runs are
   narratively non-idempotent — one rehearsal leaves an APPROVED card that
   falsifies the next take's BEFORE step, and no reset exists in the repo.
3. **[D, S]** IAM-propagation wait in `demo_hotadd.py`: after the
   `engine_iam.py` grant, probe the consult path (or `testIamPermissions`)
   until success, bounded ≤ 5 min with 15s intervals, **before** the AFTER
   query. Resource-level IAM propagation is O(minutes); today the demo
   queries immediately and can fail on a healthy system.
4. **[D, S]** `scripts/engine_iam.py`: add `raise_for_status()` + timeout to
   the getIamPolicy call. Today a failed read yields an empty policy that
   the subsequent setIamPolicy writes back — silently clobbering the
   engine's entire IAM policy.
5. **[D, S]** NEW `agents/<name>/env.manifest.json` (one per agent): the
   required baked-env key list (caseflow: PROJECT_ID, MODEL_ID, CORPUS_NAME,
   RAG_LOCATION, REGISTRY_MODE=firestore, …). `deploy_agent.py` validates
   against it (§1.3) and **stops inheriting REGISTRY_MODE/REGISTRY_URL from
   the deployer's shell** — REGISTRY_MODE currently defaults to the dead
   HTTP path (`registry_toolset.py:85`) and survives only if each deployer
   shell happens to re-export it; one fresh-shell redeploy flips the fleet
   to the unroutable B-007 URL. The manifest pins it in the repo.

### §8 RUNBOOK.md outline

**[D, S]** NEW `docs/RUNBOOK.md` (referenced from README; `docs/runbooks/`
keeps per-topic notes):

1. **Preflight (any run):** git clean + on main; `warmup.py` PASS;
   quota-window check (no CI pushes — §5.2 trigger disabled for
   demo/video); registry state check (`demo_reset.py` for demos, zero-cards
   assert for evals); env manifests valid.
2. **Deploy sequence:** per-agent order, manifest validation, post-deploy SA
   PATCH verify, smoke query, evidence lines for PROGRESS.md.
3. **Demo sequence (hot-add):** reset → warmup → BEFORE → deploy treepres
   (locked requirements) → register+approve → IAM grant → **propagation
   probe** → AFTER → artifacts persisted → PASS criteria.
4. **Video day:** min_instances on (ASK-FIRST executed, revision ids
   recorded) → full demo sequence ×1 rehearsal + `demo_reset.py` → the
   continuous take → min_instances revert. No local pytest that imports
   agent modules in the same shell as SDK scripts (§2.3).
5. **Eval run:** human per-run OK (spend rule) → preflight → run → verify
   `results.json` archived → billing-page check against the ceiling.
6. **Incident triage:** trace URL patterns, Cloud Logging filters
   (registry fail-closed line, consult_error strings), engine revision list.
7. **Rollback/reset:** demo_reset, min_instances revert, trigger re-enable,
   `wiring-deterministic-v1` tag reference.

### §9 B-009 multi-cap mitigation (per the fresh mechanism read)

The fresh ADK 2.7.1 source read **refutes the sticky-transfer framing** for
the current wiring: `mode="single_turn"` sub-agents are auto-wrapped as
`_SingleTurnAgentTool`s (llm_agent.py:1157-1170) and excluded from LLM
transfer targets; their internal errors return to the coordinator as
strings (agent_tool.py:399-400) — contained, possibly silently degrading,
not crashing. The observed ~50% multi-cap failure rate (n=2) traces to the
**uncontained consult FunctionTool leg** (§3.1's exact mechanism: cold-start
503 → uncaught exception → invocation death). Residual B-009 schema boundary
(`process_llm_agent_output` validate_schema in the single_turn wrapper) is
armed by (a) stale sessions rooting a turn at a specialist and (b)
within-invocation pydantic constraints (citations min_length=1,
extra='forbid') that constrained decoding doesn't enforce.

1. **[D, —]** Primary mitigation is §3.1 (consult containment) + §3.3
   (driver retry). No wiring change: `disallow_transfer_to_parent` would
   remove the transfer declaration from zoning's measured request bytes —
   forbidden by the constraint.
2. **[D, S]** Fresh-session-per-query stays a written driver contract
   (RUNBOOK + comment in `agent_client.py`): every driver already creates a
   fresh user_id per query, which disarms arm (a); make it an invariant,
   not an accident.
3. **[V, S]** Retest multi-cap after §3.1 lands: n ≥ 5 multi-cap runs via
   `run_case.py` (persisted per §6.2), expecting failure mode to shift from
   invocation death to contained retry/degradation. Claim only what this
   n=5 shows (evidence-precision rule).
4. **[P6, —]** Phase-6 console requirement, recorded now: the console MUST
   create a fresh session per case turn, or B-009 arm (a) re-arms through
   session reuse (`_find_agent_to_run` roots the turn at the specialist).

## Alternatives considered

- **`on_tool_error_callback` on the coordinator** instead of in-tool
  containment — cleaner and covers future tools, but edits the coordinator
  constructor (eval-path file, eval-path object) for zero pre-freeze gain
  since the callback never fires on an empty registry anyway. Deferred P6.
- **`Gemini(retry_options=...)` engine-side model retry** — rescues mid-eval
  429s but multiplies under driver retries, breaking the total-attempt cap;
  rejected pre-freeze.
- **Immediate env-override elimination** — correct end-state, but it is an
  eval-path edit 3 days before freeze whose invisibility must be proven by a
  paid A/B run; scoping now + gated elimination preserves the measurement.
- **Model quota increase request** — moot under Dynamic Shared Quota; would
  have burned days of the human's attention for nothing.
- **Workflow RetryConfig on specialists** — byte-identical requests but
  re-bills full LLM turns on retry and adds a second engine-side retry
  layer; rejected.

## Consequences

- The demo path gains containment, warmup, reset, persistence, and IAM-wait —
  the five mechanisms that individually explain every recorded demo failure.
- The measured 10/12 + 9/12 configuration remains byte-identical by
  construction on engine code, and every harness-side change is enumerated
  for sign-off rather than slipped in.
- We accept: the reserved-env-var violation persists until the gated
  elimination; interim-mode approvals stay unaudited server-side (disclosed);
  caseflow's build stays merely hand-pinned until the freeze-parity probe.
- We must not: add any retry layer not in the §3 table, set RetryConfig or
  retry_options anywhere, touch eval thresholds, or run demos outside the
  RUNBOOK sequence.

## Consolidated tier board

| Tier | Items |
|---|---|
| MUST-before-demo | §1.1 locks (treepres/safety/letters), §1.3+§7.5 manifest validation, §2.1 scoping comment, §3.1 consult containment, §3.2 stream watchdog†, §3.3 demo retry, §4.1 warmup.py, §5.1 quota filing (human)‡, §5.2 scheduling rule, §6.1 telemetry IAM‡, §6.2 reply persistence, §7.2 demo_reset.py, §7.3 IAM wait, §7.4 engine_iam fix, §8 RUNBOOK, §9.2 session contract |
| MUST-before-video | §1.2 caseflow lock (gated), §2.3 import-leak rule, §3.4 verifier retry†, §4.2 min_instances‡, §5.2 trigger pause (Terraform), §6.3 audit disclosure, §7.1 eval preflight†, §9.3 multi-cap retest |
| Phase-6-nice | §2.2 env elimination (gated)‡, §4.3 scaling introspection, §5.3 verifier pool split‡, §5.4 CI artifacts, §6.3 registry-service audit, §9.4 console session requirement |

† evidence-precision sign-off (harness change) · ‡ ASK-FIRST (IAM / billed / judge / eval spend)

## Addendum: pre-ratification amendments demanded by the verification adversaries (2026-08-26)

The coverage and regression verifiers confirmed the core design and its eval-invisibility argument, and REQUIRE these amendments before implementation:

1. **Sequencing**: the hermetic-build parity gate (SS1.2) lands BEFORE any caseflow redeploy - shipping consult containment through a non-hermetic build re-rolls the F13 dice.
2. **Watchdog thresholds are data-driven, not assumed**: measured LEGITIMATE cases ran 1326s and 2518s; the proposed 120s/630s caps would have killed counted baseline cases. Recalibrate from the archived per-case durations; make the watchdog event-aware (idle = no stream events, threshold > max single consult attempt).
3. **One retry layer per failure domain, enforced**: verifier retry lives in verify.py ONLY (the draft double-specified it in runner.py too = 16 attempts).
4. **Timeout coherence**: consult 300s x2 attempts vs 120s idle watchdog collide; bound consult attempts below the watchdog or make the watchdog consult-aware.
5. **Demo assert hardened**: the 'tree' substring check can false-PASS on a contained error envelope; parse the structured finding, require citations present and no error key.
6. **demo_reset.py is ASK-FIRST** (fixture data deletion) - flagged, never auto-run.
7. **CI preflight**: build SA lacks Firestore read; registry-zero preflight is local-only or needs a grant decision - do not silently redden CI.
8. **Warmup budget**: 2 attempts false-FAILs genuinely cold engines; use duration-based budget (~4 attempts / 3 min).
9. **A/B acceptance criteria pre-committed** before any gated change (env elimination, verifier pool split).
