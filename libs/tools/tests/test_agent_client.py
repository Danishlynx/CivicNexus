"""Unit tests for the agent-client helpers (no GCP needed)."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from civicnexus.contracts import Citation
from civicnexus.tools import (
    check_grounding,
    extract_text,
    query_json,
    query_json_with_events,
    sum_usage,
)


class _StubRemote:
    def __init__(self, events: Sequence[object]) -> None:
        self._events = events
        self.messages: list[str] = []
        self.user_ids: list[str] = []

    def stream_query(self, *, user_id: str, message: str) -> Sequence[object]:
        self.user_ids.append(user_id)
        self.messages.append(message)
        return self._events


def _text_event(text: str, **extra: object) -> dict[str, object]:
    return {"content": {"parts": [{"text": text}]}, **extra}


class TestExtractText:
    def test_dict_event(self) -> None:
        assert extract_text(_text_event("hello")) == "hello"

    def test_plain_string(self) -> None:
        assert extract_text("raw") == "raw"

    def test_event_without_content(self) -> None:
        assert extract_text({"author": "x"}) == ""

    def test_multiple_parts_concatenate(self) -> None:
        event = {"content": {"parts": [{"text": "a"}, {"function_call": {}}, {"text": "b"}]}}
        assert extract_text(event) == "ab"


class TestQueryJson:
    def test_last_json_wins_over_earlier_texts(self) -> None:
        remote = _StubRemote(
            [_text_event("thinking..."), _text_event('{"a": 1}'), _text_event('{"b": 2}')]
        )
        assert query_json(remote, "msg") == {"b": 2}

    def test_code_fences_stripped(self) -> None:
        remote = _StubRemote([_text_event('```json\n{"ok": true}\n```')])
        assert query_json(remote, "msg") == {"ok": True}

    def test_trailing_non_json_ignored(self) -> None:
        remote = _StubRemote([_text_event('{"ok": 1}'), _text_event("Anything else?")])
        assert query_json(remote, "msg") == {"ok": 1}

    def test_fresh_user_id_per_call(self) -> None:
        remote = _StubRemote([_text_event("{}")])
        query_json(remote, "m1", user_prefix="t")
        query_json(remote, "m2", user_prefix="t")
        assert len(set(remote.user_ids)) == 2
        assert all(u.startswith("t-") for u in remote.user_ids)

    def test_no_text_raises(self) -> None:
        remote = _StubRemote([{"author": "coordinator"}])
        with pytest.raises(RuntimeError, match="no text"):
            query_json(remote, "msg")

    def test_no_json_raises(self) -> None:
        remote = _StubRemote([_text_event("just prose")])
        with pytest.raises(RuntimeError, match="no JSON object"):
            query_json(remote, "msg")

    def test_with_events_returns_raw_stream(self) -> None:
        events = [_text_event("{}", usage_metadata={"prompt_token_count": 5})]
        remote = _StubRemote(events)
        parsed, raw = query_json_with_events(remote, "msg")
        assert parsed == {}
        assert raw == events


class TestSumUsage:
    def test_sums_across_events(self) -> None:
        events = [
            _text_event(
                "a", usage_metadata={"prompt_token_count": 10, "candidates_token_count": 3}
            ),
            {"usage_metadata": {"prompt_token_count": 7, "candidates_token_count": 2}},
            {"no_usage": True},
        ]
        assert sum_usage(events) == (17, 5)

    def test_missing_fields_default_zero(self) -> None:
        assert sum_usage([{"usage_metadata": {}}]) == (0, 0)


class TestCheckGrounding:
    @pytest.fixture()
    def corpus(self, tmp_path: Path) -> Path:
        (tmp_path / "17.44.100.txt").write_text(
            "No employees are allowed other than members of the resident family;",
            encoding="utf-8",
        )
        return tmp_path

    def test_verbatim_quote_passes(self, corpus: Path) -> None:
        citations = [Citation(chunk_id="17.44.100", quote="No employees are allowed")]
        assert check_grounding(citations, corpus) == []

    def test_whitespace_normalized(self, corpus: Path) -> None:
        citations = [Citation(chunk_id="17.44.100", quote="No  employees\nare allowed")]
        assert check_grounding(citations, corpus) == []

    def test_paraphrase_fails(self, corpus: Path) -> None:
        citations = [Citation(chunk_id="17.44.100", quote="Employees are not permitted")]
        failures = check_grounding(citations, corpus)
        assert len(failures) == 1 and "not verbatim" in failures[0]

    def test_unknown_section_fails(self, corpus: Path) -> None:
        citations = [Citation(chunk_id="99.99.999", quote="anything")]
        failures = check_grounding(citations, corpus)
        assert len(failures) == 1 and "unknown section" in failures[0]
