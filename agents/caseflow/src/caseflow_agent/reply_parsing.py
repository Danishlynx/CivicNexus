"""Event-stream parsing for remote agent replies (deploy-bundle-local copy).

Mirrors ``civicnexus.tools.agent_client`` extraction logic; the deployed
bundle cannot import workspace libs (schema-parity pattern, see schemas.py).
"""

import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?|```$", flags=re.MULTILINE)


def _extract_text(event: Any) -> str:
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


def last_json_object(events: list[Any]) -> dict[str, Any]:
    """The last JSON object in a reply stream; raises loud when absent."""
    texts = [t for t in (_extract_text(e).strip() for e in events) if t]
    if not texts:
        raise RuntimeError(f"remote agent produced no text; raw events: {events!r}")
    for text in reversed(texts):
        candidate = _FENCE.sub("", text).strip()
        try:
            parsed: dict[str, Any] = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return parsed
    raise RuntimeError(f"no JSON object in remote reply; texts: {texts!r}")
