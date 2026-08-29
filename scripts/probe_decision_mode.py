"""$0-class preflight: prove which decision mode the DEPLOYED engine is in.

Sends ONE minimal review query and inspects the reply shape — a fact sheet
("facts" key) means DECISION_MODE=code is live; a finding ("outcome" key)
means the engine is in model mode. Run this BEFORE any code-mode eval run:
the 2026-08-29 invalid 0/20 run measured a misconfiguration because this
check did not exist. Exit 0 only when the reply shape matches --expect.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from civicnexus.tools import query_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=["code", "model"], required=True)
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID")
    if not project:
        print("probe: PROJECT_ID required", file=sys.stderr)
        return 1
    state = json.loads(Path(".deploy/caseflow_agent.json").read_text(encoding="utf-8-sig"))
    import vertexai

    client = vertexai.Client(project=project, location=state["region"])
    remote = client.agent_engines.get(name=state["resource_name"])
    reply = query_json(
        remote,
        json.dumps(
            {
                "task": "review",
                "application": {
                    "applicant_name": "Probe Synthetic",
                    "applicant_email": "probe@example.test",
                    "permit_type": "garage_conversion",
                    "project_description": "Convert one room of the garage to a home office.",
                    "property_address": "1 Probe Way",
                    "missing_items": [],
                    "complete": True,
                },
            }
        ),
        user_prefix="probe",
    )
    observed = "code" if "facts" in reply else "model" if "outcome" in reply else "unknown"
    print(f"probe: reply keys={sorted(reply)[:6]} -> engine mode: {observed}")
    if observed != args.expect:
        print(f"probe: FAIL - expected {args.expect}, engine serves {observed}", file=sys.stderr)
        return 1
    print(f"probe: PASS - engine is in {args.expect} mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
