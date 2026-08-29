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


class TestDecisionMode:
    """ADR-008's flag. Default is `model`, and the default path must not move."""

    def test_default_is_model_and_registers_the_deciding_zoning_agent(self) -> None:
        from caseflow_agent import coordinator as coordinator_module
        from caseflow_agent.zoning import zoning_agent

        assert coordinator_module.DECISION_MODE == "model"
        assert coordinator_module.coordinator.sub_agents[1] is zoning_agent

    def test_code_mode_selects_the_extraction_agent(self) -> None:
        from caseflow_agent.coordinator import select_zoning_specialist
        from caseflow_agent.zoning import zoning_agent
        from caseflow_agent.zoning_extract import zoning_extract_agent

        assert select_zoning_specialist("code") is zoning_extract_agent
        assert select_zoning_specialist("model") is zoning_agent
        # Anything unrecognised keeps today's behaviour rather than guessing.
        assert select_zoning_specialist("") is zoning_agent
        assert select_zoning_specialist("CODE") is zoning_agent

    def test_both_specialists_fill_the_same_routing_slot(self) -> None:
        """Same name, so the coordinator instruction needs no edit either way."""
        from caseflow_agent.zoning import zoning_agent
        from caseflow_agent.zoning_extract import zoning_extract_agent

        assert zoning_extract_agent.name == zoning_agent.name == "zoning"

    def test_the_extractor_reaches_no_conclusion(self) -> None:
        from caseflow_agent.schemas import FactSheetOut
        from caseflow_agent.zoning_extract import zoning_extract_agent

        assert zoning_extract_agent.output_schema is FactSheetOut
        assert zoning_extract_agent.mode == "single_turn"
        assert lookup_municipal_code in list(zoning_extract_agent.tools)
        instruction = zoning_extract_agent.instruction
        assert isinstance(instruction, str)
        assert "YOU DO NOT DECIDE THE APPLICATION" in instruction
        # The extractor is never told the outcome vocabulary; naming an outcome
        # to a reader is what steers it (the 2026-08-28 golden-004 flip).
        for outcome_word in ("approve", "deny", "request_info"):
            assert outcome_word not in instruction.lower()

    def test_the_deciding_agent_is_untouched(self) -> None:
        from caseflow_agent.schemas import ReviewFindingOut
        from caseflow_agent.zoning import zoning_agent

        assert zoning_agent.output_schema is ReviewFindingOut
        assert isinstance(zoning_agent.instruction, str)
        assert "Decision rule, applied in order" in zoning_agent.instruction
