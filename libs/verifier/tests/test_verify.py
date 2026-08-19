"""Unit tests for the §7.3 verifier (entailment injected — no model calls)."""

from pathlib import Path

import pytest
from civicnexus.contracts import Citation, DeterminationOutcome, ReviewFinding
from civicnexus.verifier import verify_finding
from civicnexus.verifier.verify import EntailmentVerdict

ALL_OUTCOMES = [
    DeterminationOutcome.APPROVE,
    DeterminationOutcome.DENY,
    DeterminationOutcome.REQUEST_INFO,
]
SECTION_TEXT = "No employees are allowed other than members of the resident family;"


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    (tmp_path / "17.44.100.txt").write_text(SECTION_TEXT, encoding="utf-8")
    return tmp_path


def _finding(**overrides: object) -> ReviewFinding:
    defaults: dict[str, object] = {
        "outcome": DeterminationOutcome.DENY,
        "citations": [Citation(chunk_id="17.44.100", quote="No employees are allowed")],
        "rationale": "Non-resident employee stated.",
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return ReviewFinding.model_validate(defaults)


def _yes(_prompt: str) -> EntailmentVerdict:
    return EntailmentVerdict(supported=True, critique="entailed")


def _no(_prompt: str) -> EntailmentVerdict:
    return EntailmentVerdict(supported=False, critique="the cited text does not decide this")


def _run(finding: ReviewFinding, corpus: Path, entailment=_yes, outcomes=ALL_OUTCOMES):  # type: ignore[no-untyped-def]
    return verify_finding(
        finding,
        application={"permit_type": "garage_conversion"},
        permit_allowed_outcomes=outcomes,
        corpus_dir=corpus,
        entailment=entailment,
    )


def test_all_four_steps_pass(corpus: Path) -> None:
    report = _run(_finding(), corpus)
    assert report.passed
    assert report.failures == []


def test_unknown_section_fails_step_one_and_skips_model(corpus: Path) -> None:
    calls = []

    def counting(_p: str) -> EntailmentVerdict:
        calls.append(1)
        return EntailmentVerdict(supported=True, critique="")

    report = _run(
        _finding(citations=[Citation(chunk_id="99.99.999", quote="whatever")]),
        corpus,
        entailment=counting,
    )
    assert not report.passed and not report.sections_exist
    assert calls == []  # deterministic failures never spend a model call


def test_paraphrased_quote_fails_step_two(corpus: Path) -> None:
    report = _run(
        _finding(citations=[Citation(chunk_id="17.44.100", quote="Employees are banned")]),
        corpus,
    )
    assert not report.passed and not report.quotes_verbatim


def test_entailment_failure_carries_critique(corpus: Path) -> None:
    report = _run(_finding(), corpus, entailment=_no)
    assert not report.passed and not report.outcome_entailed
    assert "does not decide" in report.critique


def test_illegal_outcome_fails_step_four(corpus: Path) -> None:
    report = _run(
        _finding(outcome=DeterminationOutcome.APPROVE),
        corpus,
        outcomes=[DeterminationOutcome.DENY, DeterminationOutcome.REQUEST_INFO],
    )
    assert not report.passed and not report.outcome_legal


def test_report_payload_round_trips(corpus: Path) -> None:
    payload = _run(_finding(), corpus).as_payload()
    assert payload["passed"] is True
    assert isinstance(payload["failures"], list)
