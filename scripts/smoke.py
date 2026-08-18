"""Hello-path smoke test: query the deployed hello agent, expect a real reply.

Passing means the deployed agent produced non-empty model text end to end
(CLAUDE.md smoke contract). The query-side SDK surface was not fully
confirmable from live docs at scaffold time (deploy side was - ADR-001 item 5),
so on surface drift this script fails loudly with the available attributes
listed, to be fixed at first real deploy rather than papered over.

Trace assertion is two-step by design: this script prints where to find the
smoke trace, and scripts/verify_phase0.py requires a concrete trace id to be
recorded in PROGRESS.md - a generic list URL does not pass.
"""

import json
import sys
from pathlib import Path
from typing import Any

STATE_FILE = Path(".deploy/hello_agent.json")


def _extract_text(event: Any) -> str:
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


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if not STATE_FILE.exists():
        print(
            f"smoke: {STATE_FILE} not found - run `make deploy` first (needs PROJECT_ID).",
            file=sys.stderr,
        )
        return 1
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    resource_name, project = state["resource_name"], state["project"]

    import vertexai

    client = vertexai.Client(project=project, location=state["region"])
    remote = client.agent_engines.get(name=resource_name)

    query_fn = getattr(remote, "stream_query", None)
    if query_fn is None:
        print(
            "smoke: deployed agent object has no stream_query; query surface drifted.\n"
            f"smoke: available attrs on {type(remote)!r}: "
            f"{[a for a in dir(remote) if not a.startswith('_')]}",
            file=sys.stderr,
        )
        return 1

    events = list(query_fn(user_id="smoke", message="ping - are you alive?"))
    reply = "".join(_extract_text(e) for e in events).strip()
    if not reply:
        print(
            f"smoke: agent produced no model text in {len(events)} event(s); raw events follow.",
            file=sys.stderr,
        )
        for event in events:
            print(f"smoke:   {event!r}", file=sys.stderr)
        return 1

    print(f"smoke: agent replied: {reply!r}")
    print(
        "smoke: now open https://console.cloud.google.com/traces/list?project="
        f"{project} , click the trace for this query, and record its details URL "
        "(the one containing the trace id) in PROGRESS.md - verify-phase-0 checks for it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
