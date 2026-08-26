"""ADR-005 §4: warm every engine on the demo path until it answers.

Cold engines (scale-to-zero) were 2 of today's 6 demo failures. A ping is
one cheap model call ({"task": "__ping__"} -> {"error": "unknown task"});
ANY completed reply proves the runtime is up. Budget per engine: 4 attempts
across ~3 minutes (amendment 8: 2 attempts false-FAILs genuinely cold
engines).

Usage: uv run python scripts/warmup.py [--engines caseflow,treepres]
Exit 0 = all warm; 1 = an engine never answered (do NOT run the demo).
"""

import argparse
import json
import sys
import time
from pathlib import Path

STATE_FILES = {
    "caseflow": Path(".deploy/caseflow_agent.json"),
    "treepres": Path(".deploy/treepres_agent.json"),
    "safety": Path(".deploy/safety_agent.json"),
    "letters": Path(".deploy/letters_agent.json"),
}


def warm(name: str) -> bool:
    import vertexai

    state = json.loads(STATE_FILES[name].read_text(encoding="utf-8-sig"))
    client = vertexai.Client(project=state["project"], location=state["region"])
    remote = client.agent_engines.get(name=state["resource_name"])
    for attempt in range(1, 5):
        started = time.monotonic()
        try:
            events = list(
                remote.stream_query(
                    user_id=f"warmup-{attempt}", message=json.dumps({"task": "__ping__"})
                )
            )
            elapsed = time.monotonic() - started
            print(f"warmup: {name} WARM (attempt {attempt}, {elapsed:.1f}s, {len(events)} events)")
            return True
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"warmup: {name} attempt {attempt} failed after {elapsed:.1f}s: "
                f"{type(exc).__name__}: {str(exc)[:120]}"
            )
            if attempt < 4:
                time.sleep(min(45, 15 * attempt))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engines", default="caseflow,treepres")
    args = parser.parse_args()
    names = [n.strip() for n in args.engines.split(",") if n.strip()]
    results = {name: warm(name) for name in names}
    cold = [n for n, ok in results.items() if not ok]
    if cold:
        print(f"warmup: FAIL - still cold: {cold}", file=sys.stderr)
        return 1
    print("warmup: PASS - all requested engines answering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
