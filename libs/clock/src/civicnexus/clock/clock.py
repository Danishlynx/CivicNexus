"""CLOCK_MULTIPLIER time warp (§3.1 timers, §10 flags, Appendix A).

Real deployments run with CLOCK_MULTIPLIER=1 (default): a 12-day timer
fires in 12 days. Demos compress: multiplier 20000 fires the same timer in
~52 seconds. The multiplier is disclosed on camera per §10 — the warp
changes WHEN a real timer fires, never WHAT fires.
"""

import os
from datetime import timedelta

CLOCK_MULTIPLIER_ENV = "CLOCK_MULTIPLIER"

_SECONDS_PER_DAY = 86_400


def clock_multiplier() -> float:
    """Current multiplier; defaults to 1 (real time). Must be >= 1."""
    raw = os.environ.get(CLOCK_MULTIPLIER_ENV, "1")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{CLOCK_MULTIPLIER_ENV} must be numeric, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"{CLOCK_MULTIPLIER_ENV} must be >= 1, got {value}")
    return value


def warped_delta(days: float) -> timedelta:
    """Wall-clock delay representing `days` of case time under the warp."""
    if days <= 0:
        raise ValueError(f"days must be positive, got {days}")
    return timedelta(seconds=days * _SECONDS_PER_DAY / clock_multiplier())
