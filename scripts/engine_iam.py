"""Apply the per-resource engine-access matrix (ADR-003; human-approved grants).

Terraform's provider has no reasoning-engine IAM resource (verified
2026-08-20), so this script is the declarative source of truth for
engine-level bindings, applied via set_iam_policy — recorded per prime
directive 6. The matrix below IS the §6.1 access matrix for agent-to-agent
calls: absence of a row means deny.
"""

import json
import os
import sys
from pathlib import Path

#: caller SA (short name) -> list of state files naming callee engines.
MATRIX: dict[str, list[str]] = {
    "sa-caseflow": [".deploy/safety_agent.json", ".deploy/letters_agent.json"],
}

ROLE_ID = "civicnexusEngineCaller"


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("engine_iam: PROJECT_ID env var is required", file=sys.stderr)
        return 1

    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    role = f"projects/{project}/roles/{ROLE_ID}"

    matrix = {caller: list(files) for caller, files in MATRIX.items()}
    # demo_hotadd extends the coordinator's row at demo time (approved flow).
    hotadd_extra = os.environ.get("HOTADD_EXTRA")
    if hotadd_extra:
        matrix["sa-caseflow"].append(hotadd_extra)

    for caller, state_files in matrix.items():
        member = f"serviceAccount:{caller}@{project}.iam.gserviceaccount.com"
        for state_file in state_files:
            state = json.loads(Path(state_file).read_text(encoding="utf-8-sig"))
            engine = state["resource_name"]
            base = f"https://{region}-aiplatform.googleapis.com/v1beta1/{engine}"
            response = session.post(f"{base}:getIamPolicy", timeout=60)
            # ADR-005: an unchecked error body here parsed as an empty policy
            # and setIamPolicy would then WIPE existing bindings — never skip.
            response.raise_for_status()
            policy = response.json()
            bindings = policy.get("bindings", [])
            target = next((b for b in bindings if b.get("role") == role), None)
            if target is None:
                target = {"role": role, "members": []}
                bindings.append(target)
            if member in target["members"]:
                print(f"engine_iam: {caller} already bound on {engine}")
                continue
            target["members"].append(member)
            response = session.post(
                f"{base}:setIamPolicy",
                json={"policy": {"bindings": bindings, "etag": policy.get("etag")}},
            )
            response.raise_for_status()
            print(f"engine_iam: GRANTED {ROLE_ID}: {caller} -> {engine}")
    print("engine_iam: matrix applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
