# ADR-004: Fixed specialists attach as explicit AgentTools, not sub_agents

- **Status:** accepted — ratified by the human 2026-08-21 (B-009 fix decision:
  "Re-wire + verify"), verification gate: 12-case eval-smoke before trust.
- **Date:** 2026-08-21
- **Deciders:** proposed by Claude (build agent) from live failure evidence;
  ratified by the human.

## Context

Demo-hotadd run 2 crashed in its BEFORE review: the engine streamed a
`ValidationError: 6 validation errors for ReviewFindingOut` — the
coordinator's multi-capability composition
(`{"findings": [...], "missing_capability": ...}`) was validated against the
**zoning specialist's** strict output schema and rejected
(2 extra_forbidden + 4 missing = exactly that shape).

Mechanism (verified in installed ADK 2.7.1 source, engine traceback
matching): under the Agent Engine workflow runtime, `sub_agents` with
`mode='single_turn'` run as **nested workflow nodes**, and every node event's
final text passes `process_llm_agent_output`
(`workflow/_llm_agent_wrapper.py:354-356`), which hard-validates it against
that agent's `output_schema`. Which agent's boundary the composed text
crosses is LLM-path-dependent: run 1's BEFORE survived, run 2's did not.
Single-capability replies satisfy the schema, so seven PermitBench runs
never exposed this. As wired, every multi-capability review — including the
submission video's one continuous take — was a coin flip.

## Decision

`coordinator.tools = [AgentTool(intake), AgentTool(zoning), RegistryToolset()]`,
`sub_agents = []`.

An explicit `AgentTool` runs its agent in a **private Runner**
(`tools/agent_tool.py`, own `InMemorySessionService`) — not as a workflow
node. The specialist's `output_schema` binds exactly its own reply inside
the tool call (valid by construction; evals prove it), the result returns to
the coordinator as a dict, and the coordinator — which deliberately has **no
output_schema** (structure-tested) — always owns the final composition. No
schema-validating boundary remains on the composition path.

The coordinator instruction changed accordingly: specialists are invoked as
tools, each tool call passes the application data itself (never a draft
reply), single-capability replies return verbatim.

ADK 2.7.1 discourages explicit `AgentTool` in favor of single_turn
`sub_agents`; this ADR is the documented exception — the discouraged path is
adopted precisely because the recommended path is the crash mechanism. Live
docs support the semantic: "use agent-as-tool when the calling agent stays
in control and uses the sub-agent's output as input."

## Consequences

- Auto-transfer between specialists is gone entirely — acceptable: the
  coordinator's routing contract (task field selects the specialist) never
  used peer transfer.
- Specialist runs no longer share the parent session (private in-memory
  session per tool call) — acceptable: both specialists are single-shot
  with `include_contents` semantics that never relied on parent history.
- Verification gate before trust: `make eval-smoke` (12 cases) must hold the
  Phase 2 baseline; the hot-add demo (run 3) is the multi-capability proof.
- Revisit if ADK's workflow runtime later validates only the outermost
  node's schema (watch release notes at upgrade time).
