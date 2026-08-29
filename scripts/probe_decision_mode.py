"""$0-class preflight: prove the DEPLOYED engine + driver glue end to end.

Sends ONE minimal review query and, for --expect code, runs the reply through
the exact driver path a real run uses (fact_sheet_from_reply -> decide ->
to_review_finding). A misconfigured engine or broken glue stops here at ~2
cents instead of zeroing a billed 20-case run (the 2026-08-29 invalid 0/20
run measured a misconfiguration because this check did not exist). Exit 0
only when the deployed mode matches --expect (and, for code, the glue
composes a finding).
"""

import argparse
import json
import os
import sys
from pathlib import Path

from civicnexus.contracts.permit_types import load_permit_types, resolve_permit_type
from civicnexus.decision import decide
from civicnexus.decision.decide import fact_sheet_from_reply, to_review_finding
from civicnexus.tools import query_json

CORPUS_DIR = Path("data/corpus")

PROBE_APPLICATION = {
    "applicant_name": "Probe Synthetic",
    "applicant_email": "probe@example.test",
    "permit_type": "garage_conversion",
    "project_description": "Convert one room of the garage to a home office.",
    "property_address": "1 Probe Way",
    "missing_items": [],
    "complete": True,
}


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

    if args.expect == "code":
        # Ship the same checklist-shaped request the runner sends in code mode.
        # (The repo root is not on sys.path for scripts/ entrypoints; evals is
        # a repo-root package, so add cwd explicitly — the probe always runs
        # from the repo root, like every other script here.)
        sys.path.insert(0, os.getcwd())
        from civicnexus.contracts import Application

        from evals.runner import _review_message

        message = _review_message(Application.model_validate(PROBE_APPLICATION))
    else:
        message = json.dumps({"task": "review", "application": PROBE_APPLICATION})
    reply = query_json(remote, message, user_prefix="probe")

    observed = "code" if "facts" in reply else "model" if "outcome" in reply else "unknown"
    print(f"probe: reply keys={sorted(reply)[:6]} -> engine mode: {observed}")
    if observed != args.expect:
        print(f"probe: FAIL - expected {args.expect}, engine serves {observed}", file=sys.stderr)
        return 1

    if args.expect == "code":
        # Full driver glue on the live reply: sheet -> rules -> finding.
        sheet = fact_sheet_from_reply(reply, str(PROBE_APPLICATION["permit_type"]))
        cfgs = load_permit_types(Path("config/permit_types.yaml"))
        cfg = resolve_permit_type(cfgs, sheet.permit_type)
        result = decide(sheet, cfg, corpus_dir=CORPUS_DIR)
        finding = to_review_finding(result)
        print(
            f"probe: glue OK - {len(sheet.facts)} facts -> outcome={finding.outcome.value} "
            f"citations={[c.chunk_id for c in finding.citations]}"
        )
    print(f"probe: PASS - engine is in {args.expect} mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
