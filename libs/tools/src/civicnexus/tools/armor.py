"""Model Armor screening client — raw regional REST (ADR-006 D2; F14-immune).

Sanitize and template operations exist ONLY on the regional REP endpoint
(``modelarmor.<location>.rep.googleapis.com``); the default host 404s them
(live-verified 2026-08-26, ADR-006 Context). The endpoint is therefore a
hardcoded template parameterized by explicit ``project``/``location`` kwargs —
never resolved from env.

Screening is fail-closed with named causes (F7): a blocking-filter MATCH, any
per-filter ``EXECUTION_SKIPPED``, ``invocationResult != SUCCESS``, an HTTP
failure after the bounded retry, or an oversize payload each yield a blocked
verdict whose ``cause`` says exactly why. The verdict carries per-filter
attribution (ADR-006 D8: only pi_and_jailbreak / malicious_uri MATCHes count
toward the injection gate; SDP is advisory except at the memory-write point,
D4). Blocking is OURS: Model Armor returns verdicts, the pipeline quarantines
(D3).

Retry contract (ADR-005 §3 table, amended by ADR-006): armor client = 2
attempts, transient-only (429/5xx/transport), jittered backoff. No other
layer retries screening.
"""

import base64
import json
import random
import time
from dataclasses import dataclass, field
from typing import Any

from civicnexus.contracts import FilterMatch, ScreeningPoint
from civicnexus.otel import get_logger

_log = get_logger("armor")

ARMOR_HOST_TEMPLATE = "https://modelarmor.{location}.rep.googleapis.com/v1"
MAX_SCREEN_BYTES = 4 * 1024 * 1024  # live-verified platform cap (ADR-006 Context)
_SANITIZE_TIMEOUT_S = 30.0
_TEMPLATE_TIMEOUT_S = 15.0
_ATTEMPTS = 2
_BACKOFF_BASE_S = 2.0

#: Filters whose MATCH blocks at every screening point (ADR-006 D4).
BLOCKING_FILTERS = frozenset({"pi_and_jailbreak", "malicious_uris"})

#: sanitizeUserPrompt for content entering the system (points 1 and 4);
#: sanitizeModelResponse for model-produced content (points 2 and 3). D1.
_METHOD_FOR_POINT: dict[ScreeningPoint, str] = {
    ScreeningPoint.INBOUND_CONTENT: "sanitizeUserPrompt",
    ScreeningPoint.MEMORY_WRITE: "sanitizeUserPrompt",
    ScreeningPoint.WORKER_OUTPUT: "sanitizeModelResponse",
    ScreeningPoint.LETTER_DRAFT: "sanitizeModelResponse",
}


def blocking_filters_for(point: ScreeningPoint) -> frozenset[str]:
    """The filters whose MATCH quarantines at this point (D4: SDP blocks only
    before memory writes, where facts are structured non-PII by design)."""
    if point is ScreeningPoint.MEMORY_WRITE:
        return BLOCKING_FILTERS | {"sdp"}
    return BLOCKING_FILTERS


@dataclass(frozen=True)
class ArmorVerdict:
    """One screening outcome: what the pipeline must do, and why."""

    blocked: bool
    cause: str
    matches: list[FilterMatch] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def injection_attributed(self) -> bool:
        """True when a BLOCKING filter matched — the only thing the 15/15
        injection gate may count (ADR-006 D8); SDP/CSAM never satisfy it."""
        return any(
            m.filter in BLOCKING_FILTERS and m.match_state == "MATCH_FOUND" for m in self.matches
        )


class ArmorClient:
    """Screens text/PDF content against one Model Armor template."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        template_id: str,
        session: Any = None,
    ) -> None:
        self._base = ARMOR_HOST_TEMPLATE.format(location=location)
        self._template_path = f"projects/{project}/locations/{location}/templates/{template_id}"
        self._session = session

    def _http(self) -> Any:
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default()
            self._session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
        return self._session

    def get_template(self) -> dict[str, Any]:
        """Fetch the template (canary/preflight probe). Raises on any failure —
        a missing template is an infra problem to name, not a verdict."""
        response = self._http().get(
            f"{self._base}/{self._template_path}", timeout=_TEMPLATE_TIMEOUT_S
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def screen_text(self, text: str, *, point: ScreeningPoint) -> ArmorVerdict:
        """Screen a text payload at the given §6.3 point."""
        if len(text.encode("utf-8")) > MAX_SCREEN_BYTES:
            return self._oversize(point)
        data = {"text": text}
        return self._screen(data, point)

    def screen_pdf(self, pdf_bytes: bytes, *, point: ScreeningPoint) -> ArmorVerdict:
        """Screen a PDF payload (byteItem, base64) at the given §6.3 point."""
        if len(pdf_bytes) > MAX_SCREEN_BYTES:
            return self._oversize(point)
        data = {
            "byteItem": {
                "byteDataType": "PDF",
                "byteData": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        }
        return self._screen(data, point)

    def _oversize(self, point: ScreeningPoint) -> ArmorVerdict:
        cause = f"payload exceeds {MAX_SCREEN_BYTES} bytes - unscreenable, fail closed"
        _log.warning(f"armor oversize at {point.value}", extra={"cause": cause})
        return ArmorVerdict(blocked=True, cause=cause)

    def _screen(self, data: dict[str, Any], point: ScreeningPoint) -> ArmorVerdict:
        method = _METHOD_FOR_POINT[point]
        wrapper = "userPromptData" if method == "sanitizeUserPrompt" else "modelResponseData"
        url = f"{self._base}/{self._template_path}:{method}"
        try:
            raw = self._post_with_retry(url, {wrapper: data})
        except Exception as exc:  # fail closed on transport, loudly and by name
            cause = f"http_error after {_ATTEMPTS} attempts: {exc}"
            _log.warning(f"armor unreachable at {point.value}", extra={"cause": cause})
            return ArmorVerdict(blocked=True, cause=cause)
        return self._verdict(raw, point)

    def _post_with_retry(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = self._http().post(url, json=body, timeout=_SANITIZE_TIMEOUT_S)
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result
            except Exception as exc:
                last_error = exc
                if attempt < _ATTEMPTS:
                    time.sleep(_BACKOFF_BASE_S + random.uniform(0, _BACKOFF_BASE_S))
        raise last_error if last_error else RuntimeError("unreachable")

    def _verdict(self, raw: dict[str, Any], point: ScreeningPoint) -> ArmorVerdict:
        result = raw.get("sanitizationResult", {})
        invocation = result.get("invocationResult", "INVOCATION_RESULT_UNSPECIFIED")
        matches = _walk_filters(result.get("filterResults", {}))
        causes: list[str] = []
        if invocation != "SUCCESS":
            causes.append(f"invocationResult={invocation} - not fully screened, fail closed")
        skipped = [m.filter for m in matches if m.match_state == "EXECUTION_SKIPPED"]
        if skipped:
            causes.append(f"executionState=EXECUTION_SKIPPED for {skipped} - fail closed")
        blocking = blocking_filters_for(point)
        hits = [m for m in matches if m.filter in blocking and m.match_state == "MATCH_FOUND"]
        for hit in hits:
            suffix = f" at {hit.confidence}" if hit.confidence else ""
            causes.append(f"{hit.filter} MATCH_FOUND{suffix}")
        advisory = [
            m.filter for m in matches if m.filter not in blocking and m.match_state == "MATCH_FOUND"
        ]
        if advisory:
            _log.info(
                f"armor advisory matches at {point.value}",
                extra={"filters": json.dumps(advisory)},
            )
        blocked = bool(causes)
        cause = "; ".join(causes)
        if blocked:
            _log.warning(f"armor blocked at {point.value}", extra={"cause": cause})
        return ArmorVerdict(blocked=blocked, cause=cause, matches=matches, raw=raw)


def _walk_filters(filter_results: dict[str, Any]) -> list[FilterMatch]:
    """Flatten every filter's verdict, keeping attribution.

    Each value wraps exactly one union member (``piAndJailbreakFilterResult``,
    ``csamFilterFilterResult`` — doubled 'Filter' is the real key — etc.);
    walking values instead of key names survives all of them. A filter whose
    executionState is EXECUTION_SKIPPED is recorded with that as its
    match_state so the caller fails closed on it (unscreened is not clean).
    """
    matches: list[FilterMatch] = []
    for filter_name, wrapper in sorted(filter_results.items()):
        if not isinstance(wrapper, dict):
            continue
        for union_member in wrapper.values():
            leaf = _leaf(union_member)
            if leaf is None:
                continue
            execution = leaf.get("executionState", "")
            state = leaf.get("matchState", "MATCH_STATE_UNSPECIFIED")
            if execution == "EXECUTION_SKIPPED":
                state = "EXECUTION_SKIPPED"
            matches.append(
                FilterMatch(
                    filter=filter_name,
                    match_state=state,
                    confidence=leaf.get("confidenceLevel", ""),
                )
            )
    return matches


def _leaf(union_member: Any) -> dict[str, Any] | None:
    """The dict actually carrying matchState/executionState.

    Most filters put them directly on the union member; sdpFilterResult nests
    one level deeper (inspectResult | deidentifyResult | redactResult).
    """
    if not isinstance(union_member, dict):
        return None
    if "matchState" in union_member or "executionState" in union_member:
        return union_member
    for inner in union_member.values():
        if isinstance(inner, dict) and ("matchState" in inner or "executionState" in inner):
            return inner
    return None
