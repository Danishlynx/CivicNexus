"""CLOCK_MULTIPLIER contract tests (§10: warp changes WHEN, never WHAT)."""

import pytest
from civicnexus.clock import CLOCK_MULTIPLIER_ENV, clock_multiplier, warped_delta


def test_default_is_real_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CLOCK_MULTIPLIER_ENV, raising=False)
    assert clock_multiplier() == 1
    assert warped_delta(12).total_seconds() == 12 * 86_400


def test_demo_warp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CLOCK_MULTIPLIER_ENV, "20000")
    assert warped_delta(12).total_seconds() == pytest.approx(51.84)


def test_rejects_nonsense(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CLOCK_MULTIPLIER_ENV, "fast")
    with pytest.raises(ValueError):
        clock_multiplier()
    monkeypatch.setenv(CLOCK_MULTIPLIER_ENV, "0.5")
    with pytest.raises(ValueError):
        clock_multiplier()
    monkeypatch.setenv(CLOCK_MULTIPLIER_ENV, "1")
    with pytest.raises(ValueError):
        warped_delta(0)
