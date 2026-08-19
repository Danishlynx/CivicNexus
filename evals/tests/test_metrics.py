"""Unit tests for PermitBench metric definitions."""

import pytest
from civicnexus.contracts import DeterminationOutcome

from evals.metrics import CaseResult, compute


def _result(**overrides: object) -> CaseResult:
    defaults: dict[str, object] = {
        "case_id": "golden-001",
        "expected_outcome": DeterminationOutcome.APPROVE,
        "observed_outcome": DeterminationOutcome.APPROVE,
        "required_citations": ["17.44.100"],
        "observed_citations": ["17.44.100"],
        "latency_s": 10.0,
    }
    defaults.update(overrides)
    return CaseResult.model_validate(defaults)


def test_perfect_run_passes_gates() -> None:
    metrics = compute([_result(), _result(case_id="golden-002")])
    assert metrics.decision_accuracy == 1.0
    assert metrics.citation_precision == 1.0
    assert metrics.citation_recall == 1.0
    assert metrics.groundedness_first_pass == 1.0
    assert metrics.gates_passed


def test_wrong_outcome_hits_accuracy() -> None:
    metrics = compute(
        [_result(), _result(case_id="g2", observed_outcome=DeterminationOutcome.DENY)]
    )
    assert metrics.decision_accuracy == 0.5
    assert not metrics.gates_passed
    assert any("decision_accuracy" in f for f in metrics.gate_failures)


def test_errored_case_counts_against_everything() -> None:
    metrics = compute([_result(), _result(case_id="g2", observed_outcome=None, error="boom")])
    assert metrics.errors == 1
    assert metrics.decision_accuracy == 0.5
    assert metrics.groundedness_first_pass == 0.5


def test_extra_citation_hurts_precision_not_recall() -> None:
    metrics = compute([_result(observed_citations=["17.44.100", "17.44.005"])])
    assert metrics.citation_precision == 0.5
    assert metrics.citation_recall == 1.0


def test_missing_citation_hurts_recall_and_grounding() -> None:
    metrics = compute([_result(observed_citations=[])])
    assert metrics.citation_recall == 0.0
    assert metrics.groundedness_first_pass == 0.0


def test_grounding_failure_fails_gate() -> None:
    metrics = compute([_result(grounding_failures=["quote not verbatim in 17.44.100"])])
    assert metrics.groundedness_first_pass == 0.0
    assert not metrics.gates_passed


def test_single_canary_leak_fails_gate() -> None:
    metrics = compute([_result(canary_leaked=True)])
    assert metrics.leak_rate == 1.0
    assert any("leak_rate" in f for f in metrics.gate_failures)


def test_latency_percentiles() -> None:
    results = [_result(case_id=f"g{i}", latency_s=float(i)) for i in range(1, 11)]
    metrics = compute(results)
    assert metrics.latency_p50_s == pytest.approx(6.0, abs=1.0)
    assert metrics.latency_p95_s >= 9.0


def test_empty_results_refused() -> None:
    with pytest.raises(ValueError):
        compute([])
