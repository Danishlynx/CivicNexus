"""Structure tests for the caseflow fleet and the retrieval tool's shaping."""

import os
from types import SimpleNamespace

from caseflow_agent.rag_tool import lookup_municipal_code


class TestFleetStructure:
    def test_root_is_coordinator_with_two_specialists(self) -> None:
        from caseflow_agent.agent import root_agent

        assert root_agent.name == "coordinator"
        names = [a.name for a in root_agent.sub_agents]
        assert names == ["intake", "zoning"]

    def test_specialists_run_single_turn(self) -> None:
        from caseflow_agent.intake import intake_agent
        from caseflow_agent.zoning import zoning_agent

        assert intake_agent.mode == "single_turn"
        assert zoning_agent.mode == "single_turn"

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
