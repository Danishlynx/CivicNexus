"""Unit tests for structured JSON logging."""

import json

import pytest
from civicnexus.otel import get_logger


@pytest.fixture()
def fresh_logger_name(request: pytest.FixtureRequest) -> str:
    return f"test-{request.node.name}"


def _last_json_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])  # type: ignore[no-any-return]


def test_emits_valid_json_with_cloud_logging_fields(
    capsys: pytest.CaptureFixture[str], fresh_logger_name: str
) -> None:
    log = get_logger(fresh_logger_name)
    log.info("hello case", extra={"case_id": "case-0001"})
    entry = _last_json_line(capsys)
    assert entry["severity"] == "INFO"
    assert entry["message"] == "hello case"
    assert entry["service"] == fresh_logger_name
    assert entry["case_id"] == "case-0001"
    assert "time" in entry


def test_extras_cannot_clobber_canonical_fields(
    capsys: pytest.CaptureFixture[str], fresh_logger_name: str
) -> None:
    log = get_logger(fresh_logger_name)
    log.info("real message", extra={"severity": "FORGED", "service": "forged", "case_id": "c-1"})
    entry = _last_json_line(capsys)
    assert entry["severity"] == "INFO"
    assert entry["service"] == fresh_logger_name
    assert entry["message"] == "real message"
    assert entry["case_id"] == "c-1"


def test_error_severity_mapped(capsys: pytest.CaptureFixture[str], fresh_logger_name: str) -> None:
    log = get_logger(fresh_logger_name)
    log.error("boom")
    assert _last_json_line(capsys)["severity"] == "ERROR"


def test_repeated_get_logger_does_not_stack_handlers(fresh_logger_name: str) -> None:
    first = get_logger(fresh_logger_name)
    second = get_logger(fresh_logger_name)
    assert first is second
    assert len(second.handlers) == 1


def test_logger_does_not_propagate_to_root(fresh_logger_name: str) -> None:
    assert get_logger(fresh_logger_name).propagate is False


def test_severity_falls_back_to_default_for_custom_levels(
    capsys: pytest.CaptureFixture[str], fresh_logger_name: str
) -> None:
    log = get_logger(fresh_logger_name, level=5)
    log.log(5, "trace-ish")
    assert _last_json_line(capsys)["severity"] == "DEFAULT"


def test_exception_included(capsys: pytest.CaptureFixture[str], fresh_logger_name: str) -> None:
    log = get_logger(fresh_logger_name)
    try:
        raise ValueError("bad parcel")
    except ValueError:
        log.exception("failed")
    entry = _last_json_line(capsys)
    assert entry["severity"] == "ERROR"
    assert "bad parcel" in str(entry["exception"])
