"""Unit tests for the §7.3 verifier (model checks injected — no model calls)."""

from pathlib import Path

import pytest
from civicnexus.contracts import Citation, DeterminationOutcome, ReviewFinding
from civicnexus.verifier import verify_finding
from civicnexus.verifier.verify import EntailmentVerdict, OveraskVerdict

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


def _absent(_prompt: str) -> OveraskVerdict:
    return OveraskVerdict(already_stated=False, quote="", critique="genuinely missing")


APPLICATION: dict[str, object] = {
    "permit_type": "garage_conversion",
    "project_description": "The office occupies one room of 120 square feet in the garage.",
}


def _run(  # type: ignore[no-untyped-def]
    finding: ReviewFinding, corpus: Path, entailment=_yes, outcomes=ALL_OUTCOMES, overask=_absent
):
    return verify_finding(
        finding,
        application=APPLICATION,
        permit_allowed_outcomes=outcomes,
        corpus_dir=corpus,
        entailment=entailment,
        overask=overask,
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


def test_unknown_permit_type_fails_honestly_without_outcome_steering(corpus: Path) -> None:
    # Empty allowed list = unconfigured permit type. The failure text must NOT
    # read "pick a different outcome" — that wording measurably flipped a
    # correct request_info to a wrong approve on retry (2026-08-28).
    report = _run(_finding(), corpus, outcomes=[])
    assert not report.passed and not report.outcome_legal
    assert any("not configured" in f for f in report.failures)
    assert not any("is not allowed for this permit type" in f for f in report.failures)


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
    assert payload["no_overask"] is True
    assert isinstance(payload["failures"], list)


def _request_info() -> ReviewFinding:
    return _finding(
        outcome=DeterminationOutcome.REQUEST_INFO,
        rationale="The floor area of the office is not stated.",
    )


def test_overask_confirmed_quote_fails_step_five(corpus: Path) -> None:
    def stated(_p: str) -> OveraskVerdict:
        return OveraskVerdict(
            already_stated=True, quote="one room of 120 square feet", critique="stated"
        )

    report = _run(_request_info(), corpus, overask=stated)
    assert not report.passed and not report.no_overask
    assert any("over-ask" in f for f in report.failures)
    assert "120 square feet" in report.critique  # retry critique names the fact


def test_overask_hallucinated_quote_never_fires(corpus: Path) -> None:
    def hallucinated(_p: str) -> OveraskVerdict:
        return OveraskVerdict(
            already_stated=True, quote="a fact the application never states", critique=""
        )

    report = _run(_request_info(), corpus, overask=hallucinated)
    # Code confirms quotes; the model alone cannot fail a finding.
    assert report.passed and report.no_overask


def test_overask_absent_information_passes(corpus: Path) -> None:
    report = _run(_request_info(), corpus, overask=_absent)
    assert report.passed and report.no_overask


def test_overask_not_called_for_decided_outcomes(corpus: Path) -> None:
    calls: list[int] = []

    def counting(_p: str) -> OveraskVerdict:
        calls.append(1)
        return OveraskVerdict(already_stated=False, quote="")

    report = _run(_finding(), corpus, overask=counting)  # DENY finding
    assert report.passed
    assert calls == []


def test_overask_skipped_when_entailment_fails(corpus: Path) -> None:
    calls: list[int] = []

    def counting(_p: str) -> OveraskVerdict:
        calls.append(1)
        return OveraskVerdict(already_stated=False, quote="")

    report = _run(_request_info(), corpus, entailment=_no, overask=counting)
    assert not report.passed
    assert calls == []  # a failing finding never pays the second model call
