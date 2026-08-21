# ADR-003: Agent-to-agent auth via resource-level IAM; hot-add via dynamic toolset

- **Status:** accepted — **ratified by the human 2026-08-20** (rulings: auth
  planes; dynamic toolset), with two conditions incorporated below: decision 2
  is "SA as baseline" with Agent Identity preferred pending a two-principal
  spike, and the dynamic toolset's approved-only filter is a mandatory
  tool-poisoning defense.
- **Date:** 2026-08-20
- **Deciders:** proposed by Claude (build agent) per prime directive 10;
  ratified by the human

## Context

Phase 3 build-time verification (live docs + installed-SDK source; URLs and
line numbers in the research transcript) found that ARCHITECTURE.md §6.1's
"Google-signed ID tokens (audience-checked) on every internal call" does not
exist for Agent Engine → Agent Engine calls, and that §11's hot-add cannot be
built on `sub_agents`.

## Deltas and decisions

1. **Engine↔engine auth = OAuth access tokens + resource-level IAM.** Agent
   Engine's A2A endpoint (`…/reasoningEngines/{id}/a2a`, v1beta1, HTTP+JSON,
   no streaming) authenticates with cloud-platform access tokens; no ID-token
   or audience mechanism exists in the platform or the ADK a2a package.
   Authorization is `aiplatform.reasoningEngines.query`, grantable **per agent
   resource** — a deny-by-default per-agent matrix. §6.1's intent (per-agent
   identity, least privilege, verified caller) is preserved; the mechanism
   changes. Audience-checked ID tokens remain the pattern for the Cloud Run
   legs (registry, gateway) only.
2. **Per-agent identity: dedicated service accounts as BASELINE — not final.**
   Bound via `.agent_engine_config.json` → `"service_account"` (the
   `adk deploy` CLI passes the config verbatim to `agent_engines.update`; the
   SDK field is documented). The newer "Agent Identity" principal
   (`identity_type: AGENT_IDENTITY`) **remains PREFERRED pending a
   two-principal spike**: its documented trust domain appears
   organization-scoped (`org-ORG_ID`) and this is a personal, org-less
   project — whether it works here is an empirical question the spike
   answers, not an assumption. Until that spike runs, SAs are the working
   baseline (human ruling, 2026-08-20).
   Caveat (source-verified): the CLI creates the instance first and applies
   config via update, so a new instance briefly runs under the default
   service agent before its own SA binds. Acceptable for this project;
   noted honestly.
3. **Hot-add = registry-backed dynamic toolset.** `sub_agents` wiring is fixed
   at deploy (Pydantic parent-linking at construction). Tools, however,
   re-resolve per invocation (`canonical_tools` cached per-run only). The
   coordinator therefore carries a custom `BaseToolset` that queries the
   registry and wraps remote agents as `AgentTool`s — a newly approved agent
   is dispatchable on the next case, no redeploy.
   **Mandatory (human ruling, 2026-08-20): the toolset filters to
   `status == APPROVED` before anything becomes a tool.** That filter is the
   tool-poisoning defense (§6.7 threat "lookalike/unapproved agent
   registered") — it is not an option or an optimization. Our
   Firestore-backed registry service remains the governance source of truth
   (approval lifecycle, §6.2 selfhosted mode); Google's managed Agent
   Registry (auto-registration on deploy, GA status unconfirmed) is the §6.2
   `managed` adapter's concern, attempted only in Phase 6 per plan.
4. **Highest-risk unknown, spiked before any dependent code:** whether a
   CLI-deployed ADK agent actually exposes a working `/a2a` endpoint (the
   api_server mounts A2A routes only for agent dirs containing `agent.json`,
   and the CLI never populates `spec.agent_card` on its own). Spike: deploy a
   throwaway agent carrying `agent.json` + `agent_card` config; GET
   `{a2a_url}/v1/card` with an ADC bearer token. Result recorded below.

## Spike result (2026-08-20, evidence-precision record)

Four variants ran against `adk deploy agent_engine` (ADK 2.7.1 CLI,
throwaway agent `a2a-spike`):

| Variant | Setup | Result |
|---|---|---|
| V1 | `agent.json` + `.agent_engine_config.json` (with `agent_card`), config passed via `--agent_engine_config_file` relative path | deploy FAILED — CLI could not find the config file at the explicit path |
| V2 | same files, default config discovery | deploy FAILED — the CLI's `AgentEngineConfig` validator rejects the `agent_card` key (`extra_forbidden`); the SDK `update` config validator rejects it identically |
| V3 | `agent.json` only | deploy SUCCEEDED (instance `…6606976`); `GET {a2a}/v1/card` → **400**; `GET {a2a}/.well-known/agent-card.json` → 404 |
| V4 | V3 instance + raw REST `PATCH spec.agent_card` (accepted, HTTP 200) | card routes unchanged (400/404); `POST {a2a}/v1/message:send` (shape: `{"message":{messageId,role,parts:[{text}]}}`) → **400** |

**Exact claims these tests prove:**
- A CLI-deployed ADK 2.7.1 agent did **not** serve a working A2A card or
  message endpoint under any variant tested. The platform-side `/a2a` route
  surface exists (400, not 404, on `v1/card`).
- The `agent_card` config key is rejected by both CLI and SDK client
  validators in the installed versions; only raw REST accepts the field.

**What these tests do NOT prove:** that A2A is broken per se. Not isolated:
whether the V4 PATCH actually persisted `spec.agentCard` (not re-read);
whether the 400 on `message:send` reflects a wrong request shape rather than
a dead endpoint; whether an SDK-deployed `AdkApp` (as opposed to CLI
source-deploy) behaves differently.

**Consequence:** the hot-add dynamic toolset must not depend on the A2A
protocol transport in Phase 3. **Ruled 2026-08-20 (human delegation of the
flagged choice):** the toolset wraps approved remote engines via the
**proven** `:streamQuery` surface — the same transport the eval runner
exercises daily — with A2A-proper deferred to the Phase 6 managed-mode
attempt. The approved-only filter (decision 3) applies unchanged. Spike
instance deleted after the test.

## Consequences

- The IAM matrix (Appendix B) gains one row per caller→callee pair with
  `reasoningEngines.query`; the deliberate-deny test asserts both the 403 and
  its audit log entry — stronger evidence than an application-layer denial.
- The gateway's role for engine↔engine legs shifts to policy/screening/audit
  (allowlists, Model Armor, rate limits), with platform IAM enforcing
  identity underneath — defense in depth rather than a single choke point.

## Addendum (2026-08-21): B-007 Firestore-direct interim for registry reads

The registry service deploys healthy but its run.app URLs are unroutable at
Google's edge — **project-wide**, proven by an identical us-east1 deployment
404ing the same way (B-007; east service destroyed after the test). Human
ruling 2026-08-21: "Try second region, else Firestore-direct."

**Interim mechanism (`REGISTRY_MODE=firestore`):**
- The coordinator's dynamic toolset reads `registry_agents` directly from
  Firestore. The mandatory approved-only filter (decision 3) moves INTO the
  query (`status == "APPROVED"`, plus capability `array_contains`) — the
  tool-poisoning defense is structurally identical.
- Demo drivers register/approve through the `RegistryStore` library (same
  lifecycle guards, same transition table, same audit fields) under the
  human's ADC identity instead of the HTTP API.

**Honest deviation:** reads bypass the Cloud Run policy boundary
(per-principal `run.invoker` IAM). Firestore offers no row-level IAM, so
sa-caseflow's read grant is datastore-scoped (limitation already acknowledged
in §6.1). Writes in the interim happen only under the human's own identity.

**Reversion condition:** flip `REGISTRY_MODE` back to `http` and redeploy the
coordinator the moment the edge routes the service. The registry service and
its invoker policy stay deployed and authoritative throughout; the interim is
a read-path detour, not a redesign.
