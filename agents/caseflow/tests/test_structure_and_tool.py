"""Structure tests for the caseflow fleet and the retrieval tool's shaping."""

import os
from types import SimpleNamespace

from caseflow_agent.rag_tool import lookup_municipal_code


class TestFleetStructure:
    def test_root_is_coordinator_with_specialists_as_agent_tools(self) -> None:
        """ADR-004: specialists are explicit AgentTools, never sub_agents —
        sub_agents become schema-validated workflow nodes on the engine and
        nondeterministically reject the composed reply (B-009)."""
        from caseflow_agent.agent import root_agent
        from google.adk.tools.agent_tool import AgentTool

        assert root_agent.name == "coordinator"
        assert root_agent.sub_agents == []
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        assert [t.agent.name for t in agent_tools] == ["intake", "zoning"]

    def test_coordinator_composes_unvalidated(self) -> None:
        """The composing agent must never carry an output_schema — that is
        the exact boundary that crashed run 2 (B-009)."""
        from caseflow_agent.agent import root_agent

        assert root_agent.output_schema is None

    def test_specialists_carry_no_mode(self) -> None:
        """ADR-004: AgentTool's private Runner REJECTS single_turn roots
        (runners.py root-mode gate) — mode must stay unset on fresh import
        so the Runner defaults it. This test enshrines the fix for the
        blocker the pre-deploy verification caught."""
        from caseflow_agent.intake import intake_agent
        from caseflow_agent.zoning import zoning_agent

        assert intake_agent.mode is None
        assert zoning_agent.mode is None

    def test_zoning_carries_the_retrieval_tool(self) -> None:
        from caseflow_agent.zoning import zoning_agent

        assert lookup_municipal_code in list(zoning_agent.tools)

    def test_output_schemas_enforced(self) -> None:
        from caseflow_agent.intake import intake_agent
        from caseflow_agent.schemas import ApplicationOut, ReviewFindingOut
        from caseflow_agent.zoning import zoning_agent

        assert intake_agent.output_schema is ApplicationOut
        assert zoning_agent.output_schema is ReviewFindingOut


class _StubRag:
    def retrieve_contexts(self, **_kwargs: object) -> SimpleNamespace:
        contexts = [
            SimpleNamespace(
                source_display_name="17.44.100",
                text="Not more than one room in a dwelling or in an accessory structure",
                score=0.2,
            ),
            SimpleNamespace(
                source_display_name="17.44.005", text="Accessory dwelling units", score=0.4
            ),
        ]
        return SimpleNamespace(contexts=SimpleNamespace(contexts=contexts))


class TestRagTool:
    def test_shapes_sections_with_stable_ids(self) -> None:
        os.environ.setdefault("CORPUS_NAME", "projects/p/locations/l/ragCorpora/1")
        result = lookup_municipal_code(
            "home occupation in a garage", _client=SimpleNamespace(rag=_StubRag())
        )
        assert result["sections"][0] == {
            "section": "17.44.100",
            "text": "Not more than one room in a dwelling or in an accessory structure",
        }
        assert len(result["sections"]) == 2
