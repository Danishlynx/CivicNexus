"""Loop-signature circuit breaker (§7.2; ADR-006 D12) — detection library.

The coordinator-side reroute/escalate embedding is Phase 6+ (a caseflow
redeploy, gated by ADR-005); this library detects the loop signature and the
DRILL composes the consequences — publish ``incident.raised`` with the drill's
case context and machine-quarantine the offending card via
``RegistryStore.change_status(APPROVED -> QUARANTINED, human_actor=False)``,
the one registry move contracts permit a machine (MACHINE_ALLOWED_CHANGES).
Composition lives in the driver so libs/tools never imports the registry
service.
"""

import hashlib
import json
from typing import Any

from civicnexus.otel import get_logger

_log = get_logger("breaker")

#: §7.2: three identical agent+tool+normalized-args calls on one case = loop.
LOOP_THRESHOLD = 3


def loop_signature(agent_id: str, tool: str, args: dict[str, Any]) -> str:
    """The §7.2 loop signature: sha256 over agent, tool, and normalized args."""
    normalized = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{agent_id}\x1f{tool}\x1f{normalized}".encode()).hexdigest()
    return f"{agent_id}/{tool}/sha256:{digest[:16]}"


class CircuitBreaker:
    """Counts identical call signatures per case; opens at LOOP_THRESHOLD.

    ``observe`` returns True exactly once per (case, signature) — at the call
    that trips the circuit — so a driver acts once, not on every subsequent
    identical call.
    """

    def __init__(self, *, threshold: int = LOOP_THRESHOLD) -> None:
        self._threshold = threshold
        self._counts: dict[tuple[str, str], int] = {}
        self._open: set[tuple[str, str]] = set()

    def observe(self, case_id: str, agent_id: str, tool: str, args: dict[str, Any]) -> bool:
        """Record one call; True when this call OPENS the circuit for its case."""
        signature = loop_signature(agent_id, tool, args)
        key = (case_id, signature)
        self._counts[key] = self._counts.get(key, 0) + 1
        if self._counts[key] >= self._threshold and key not in self._open:
            self._open.add(key)
            _log.warning(
                f"circuit OPEN case={case_id}",
                extra={
                    "case_id": case_id,
                    "signature": signature,
                    "count": self._counts[key],
                    "threshold": self._threshold,
                },
            )
            return True
        return False

    def is_open(self, case_id: str, agent_id: str, tool: str, args: dict[str, Any]) -> bool:
        """Whether this exact signature's circuit is already open for the case."""
        return (case_id, loop_signature(agent_id, tool, args)) in self._open
