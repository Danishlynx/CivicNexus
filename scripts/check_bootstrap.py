"""Verify `make bootstrap` outcomes from Terraform outputs.

Passing means the baseline applied cleanly and the budget-alert proof exists
(CLAUDE.md make-targets contract). Runs after `terraform apply`, so state and
outputs are expected to be present.
"""

import json
import subprocess
import sys

REQUIRED_OUTPUTS = (
    "budget_name",
    "budget_threshold_percents",
    "enabled_apis",
    "agent_staging_bucket",
)
EXPECTED_THRESHOLD_COUNT = 3  # $50/$100/$140 per the CLAUDE.md bootstrap contract


def main() -> int:
    try:
        result = subprocess.run(
            ["terraform", "-chdir=infra/terraform", "output", "-json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        print("check_bootstrap: terraform is not on PATH", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(f"check_bootstrap: terraform output failed:\n{result.stderr}", file=sys.stderr)
        return 1

    outputs: dict[str, dict[str, object]] = json.loads(result.stdout or "{}")
    missing = [k for k in REQUIRED_OUTPUTS if not outputs.get(k, {}).get("value")]
    if missing:
        print(f"check_bootstrap: missing terraform outputs: {missing}", file=sys.stderr)
        return 1

    thresholds = outputs["budget_threshold_percents"]["value"]
    if not isinstance(thresholds, list) or len(thresholds) != EXPECTED_THRESHOLD_COUNT:
        print(
            f"check_bootstrap: expected {EXPECTED_THRESHOLD_COUNT} budget alert "
            f"thresholds, got {thresholds!r}",
            file=sys.stderr,
        )
        return 1

    print(f"check_bootstrap: budget={outputs['budget_name']['value']}")
    print(f"check_bootstrap: alert thresholds (fractions)={thresholds}")
    print(f"check_bootstrap: staging bucket={outputs['agent_staging_bucket']['value']}")
    apis = outputs["enabled_apis"]["value"]
    print(f"check_bootstrap: {len(apis) if isinstance(apis, list) else '?'} APIs enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
