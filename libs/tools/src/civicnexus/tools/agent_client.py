"""Helpers for driving deployed Agent Engine apps and checking grounding.

Shared by the demo driver (scripts/run_case.py) and the eval runner
(evals/runner.py) so both speak to the fleet identically.
"""

import json
import queue
import re
import secrets
import threading
from pathlib import Path
from typing import Any

from civicnexus.contracts import Citation

_FENCE = re.compile(r"^```(?:json)?|```$", flags=re.MULTILINE)

# ADR-005 §3.2 stream watchdog: idle threshold (no NEW event), NOT a total
# cap — measured LEGITIMATE runs took 1326s/2518s total, while the F11 hang
# produced ZERO events for 81 minutes. 600s idle > the consult tool's worst
# single bounded attempt (500s), so contained engine-side retries never trip
# it. Evidence-precision: calibrated against the archived run durations.
STREAM_IDLE_TIMEOUT_S = 600.0
_SENTINEL = object()


def _iter_with_idle_watchdog(stream: Any, idle_timeout_s: float) -> Any:
    """Yield stream items; raise TimeoutError if the gap between items
    exceeds idle_timeout_s (a hung stream, not a slow one)."""
    q: queue.Queue[Any] = queue.Queue()
    error: list[BaseException] = []

    def _pump() -> None:
        try:
            for item in stream:
                q.put(item)
        except BaseException as exc:  # propagate the real stream error
            error.append(exc)
        finally:
            q.put(_SENTINEL)

    worker = threading.Thread(target=_pump, daemon=True)
    worker.start()
    while True:
        try:
            item = q.get(timeout=idle_timeout_s)
        except queue.Empty:
            raise TimeoutError(
                f"stream idle for {idle_timeout_s:.0f}s (no events) - hung stream"
            ) from None
        if item is _SENTINEL:
            if error:
                raise error[0]
            return
        yield item


def extract_text(event: Any) -> str:
    """Best-effort pull of model text from an ADK event (dict or object shape)."""
    if isinstance(event, str):
        return event
    content = event.get("content") if isinstance(event, dict) else getattr(event, "content", None)
    if content is None:
        return ""
    parts = content.get("parts") if isinstance(content, dict) else getattr(content, "parts", None)
    if not parts:
        return ""
    texts = []
    for part in parts:
        text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
        if isinstance(text, str):
            texts.append(text)
    return "".join(texts)


def query_json_with_events(
    remote: Any, message: str, *, user_prefix: str = "drive"
) -> tuple[dict[str, Any], list[Any]]:
    """Send one message in a fresh session; return (last JSON object, raw events).

    Fresh identity per query: a shared session parks the conversation with the
    previously delegated specialist and derails coordinator routing. A
    delegation run emits several text events (specialist output, coordinator
    echo); the final valid JSON is the authoritative reply.
    """
    stream = remote.stream_query(user_id=f"{user_prefix}-{secrets.token_hex(4)}", message=message)
    events = list(_iter_with_idle_watchdog(stream, STREAM_IDLE_TIMEOUT_S))
    texts = [t for t in (extract_text(e).strip() for e in events) if t]
    if not texts:
        raise RuntimeError(f"agent produced no text; raw events: {events!r}")
    for text in reversed(texts):
        candidate = _FENCE.sub("", text).strip()
        try:
            parsed: dict[str, Any] = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return parsed, events
    raise RuntimeError(f"no JSON object in agent reply; texts: {texts!r}")


def query_json(remote: Any, message: str, *, user_prefix: str = "drive") -> dict[str, Any]:
    """Like :func:`query_json_with_events`, returning just the JSON object."""
    parsed, _ = query_json_with_events(remote, message, user_prefix=user_prefix)
    return parsed


def sum_usage(events: list[Any]) -> tuple[int, int]:
    """Total (tokens_in, tokens_out) across events carrying usage_metadata."""
    tokens_in = tokens_out = 0
    for event in events:
        usage = (
            event.get("usage_metadata")
            if isinstance(event, dict)
            else getattr(event, "usage_metadata", None)
        )
        if not usage:
            continue
        prompt = (
            usage.get("prompt_token_count")
            if isinstance(usage, dict)
            else getattr(usage, "prompt_token_count", None)
        )
        candidates = (
            usage.get("candidates_token_count")
            if isinstance(usage, dict)
            else getattr(usage, "candidates_token_count", None)
        )
        tokens_in += int(prompt or 0)
        tokens_out += int(candidates or 0)
    return tokens_in, tokens_out


def check_grounding(citations: list[Citation], corpus_dir: Path) -> list[str]:
    """Return grounding failures: unknown sections or non-verbatim quotes."""
    failures = []
    for citation in citations:
        section_file = corpus_dir / f"{citation.chunk_id}.txt"
        if not section_file.exists():
            failures.append(f"citation names unknown section {citation.chunk_id}")
            continue
        section_text = " ".join(section_file.read_text(encoding="utf-8").split())
        quote = " ".join(citation.quote.split())
        if quote not in section_text:
            failures.append(f"quote not verbatim in {citation.chunk_id}: {citation.quote[:60]!r}")
    return failures
