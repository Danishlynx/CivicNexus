# ADR-001: Live-docs deltas vs ARCHITECTURE.md at build start

- **Status:** accepted (delta record); the managed-bind decision it surfaces is
  **deferred to the human at the Phase 3 gate**
- **Date:** 2026-08-18
- **Deciders:** Claude (build agent); flagged for Danish at the next gate

## Context

Prime directive 10 requires verifying Google's fast-moving product details against
live docs at build time and recording contradictions as ADRs. Build-start research
(live fetches, 2026-08-18, source URLs in the research transcripts) found the
following confirmed deltas against ARCHITECTURE.md.

## Deltas found

1. **Managed Agent Gateway and Agent Registry are GA (since 2026-06-18)** — §6.2
   assumes both are preview with access "not guaranteed". Both ship GA; Agent
   Registry has Terraform support and A2A v1.0; Model Armor on Agent Gateway is GA
   (2026-06-24). Search-engine snippets still claim preview; the official
   release-notes feed and absence of Pre-GA banners on four doc pages say GA.
   Confirm in-console once a project exists.
2. **Product rebrand:** the umbrella is now "Gemini Enterprise Agent Platform"
   (Apr 2026); "Vertex AI Agent Engine Sessions/Memory Bank" are now "Agent
   Platform Sessions/Memory Bank"; docs moved to
   `docs.cloud.google.com/gemini-enterprise-agent-platform/...`. **ADK class names
   are unchanged** (`VertexAiSessionService`, `VertexAiMemoryBankService`, kwarg
   `agent_engine_id`) — spec code references stay valid.
3. **Model Armor specifics** confirmed: service GA, `modelarmor.googleapis.com`;
   sanitize calls require the **regional** endpoint
   `modelarmor.us-central1.rep.googleapis.com`; us-central1 has **no image
   modality** (text injection screening is fine — our drill is text-based);
   floor-setting violations only surface in SCC on paid tiers, so the incident
   view must be driven by our own `incidents/` store + Cloud Logging (which §3.2
   already prescribes); Python client `google-cloud-modelarmor` is pre-GA (0.7.1)
   and must be pinned; Terraform `google_model_armor_template` exists in the GA
   provider since 6.43.0.
4. **Terraform provider** is at 7.44.0; `google_billing_budget` with user ADC
   requires `user_project_override = true` + `billing_project` in the provider
   block or the API 403s (already reflected in `infra/terraform/providers.tf`).
5. **ADK CLI flag drift (v2.7.1 source is authoritative; published docs lag):**
   on `adk deploy agent_engine`, `--trace_to_cloud` is deprecated in favor of
   `--otel_to_cloud`, and `--staging_bucket` is deprecated on the CLI path (the
   SDK path still requires `staging_bucket` in `config`). SDK deploy surface is
   `vertexai.Client(...)` + `client.agent_engines.create(agent=AdkApp(...),
   config={...})` with `google-cloud-aiplatform[agent_engines,adk]>=1.112`.
6. **`gemini-3.5-flash` confirmed valid** (used in Google's own Agent Runtime
   quickstart) — but priced ~$1.50/$9.00 per 1M tokens (Developer-API list;
   Vertex table unfetchable, treat as approximate). `gemini-3.5-flash-lite`
   (~$0.30/$2.50, "most cost-efficient, optimized for high-volume agentic
   tasks") is the cost-guard candidate for high-volume paths. **Decision for the
   human at the Phase 1 gate**; `MODEL_ID` env var remains the single override.
7. **`google_vertex_ai_reasoning_engine` exists in the GA provider** — agent
   deployment could be Terraform-native. Phase 0 uses the SDK path per the
   `make deploy` contract (deploy from source); revisit at Phase 3.

## Decision

Keep the §6.2 port/adapter design and **build `GATEWAY_MODE=selfhosted` first**,
unchanged: it is the reversible path, is demo-complete regardless, and the GA
signal — though high-confidence — is unverified in-console. The delta changes the
*timing question* (managed bind could be attempted at Phase 3 rather than Phase 6)
and that question goes to the human at the Phase 3 gate.

## Alternatives considered

- Switch to managed Gateway/Registry now — rejected: violates phase discipline,
  and GA status is not yet confirmed in-console from this account.
- Ignore the delta until Phase 6 — rejected: directive 10 requires recording it,
  and the human should decide with it on the table at Phase 3 (registry +
  governance phase), not after.

## Consequences

- Phase 3 gate review gains one agenda item: selfhosted vs managed bind timing.
- Phase 4 memory work can rely on unchanged ADK service classes.
- Phase 5 must use the regional Model Armor endpoint and text-modality screening,
  and pin `google-cloud-modelarmor`.

## Sources (all fetched live 2026-08-18)

- ADK package/versions: https://pypi.org/project/google-adk/ ·
  https://raw.githubusercontent.com/google/adk-python/v2.7.1/src/google/adk/cli/cli_tools_click.py
  (authoritative for the CLI flag deprecations; published docs lag)
- ADK docs (relocated): https://adk.dev/deploy/agent-runtime/deploy/ ·
  https://adk.dev/integrations/cloud-trace/ · https://adk.dev/sessions/memory/
- Agent Engine/Runtime deploy + model string: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk ·
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent ·
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/tracing
- Sessions/Memory Bank: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions/manage-with-adk ·
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart
- Gateway/Registry GA: https://docs.cloud.google.com/feeds/gemini-enterprise-agent-platform-release-notes.xml ·
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview ·
  https://docs.cloud.google.com/agent-registry/overview
- Model Armor: https://docs.cloud.google.com/model-armor/release-notes ·
  https://docs.cloud.google.com/model-armor/sanitize-prompts-responses ·
  https://docs.cloud.google.com/model-armor/manage-templates ·
  https://docs.cloud.google.com/model-armor/feature-availability-by-region ·
  https://pypi.org/project/google-cloud-modelarmor/
- Terraform provider/budget: https://registry.terraform.io/v1/providers/hashicorp/google ·
  https://raw.githubusercontent.com/hashicorp/terraform-provider-google/main/website/docs/r/billing_budget.html.markdown ·
  https://docs.cloud.google.com/billing/docs/access-control ·
  https://docs.cloud.google.com/billing/docs/how-to/budget-api-setup
- Model pricing (Developer-API list; Vertex table unfetchable):
  https://ai.google.dev/gemini-api/docs/pricing.md.txt
