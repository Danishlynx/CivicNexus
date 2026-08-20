"""The deliberate-deny test (§6.1, §11 Phase 3 exit): prove the matrix, both ways.

POSITIVE: impersonating sa-caseflow, query the safety engine — the matrix
grants it, so a reply must come back.
NEGATIVE: impersonating sa-safety, attempt the letters engine — no grant
exists, so the platform must refuse (403) AND the refusal must appear in the
Data Access audit log. Specialists never call each other; the denial is the
architecture working.

Passing means: positive returned text, negative was denied, and the audit
entry for the denial was found.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


def _impersonated_token(sa_email: str) -> str:
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.transport.requests import Request

    source, _ = google.auth.default()
    target = impersonated_credentials.Credentials(  # type: ignore[no-untyped-call]
        source_credentials=source,
        target_principal=sa_email,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=300,
    )
    target.refresh(Request())  # type: ignore[no-untyped-call]
    return str(target.token)


def _query(engine: str, region: str, token: str, message: str) -> requests.Response:
    return requests.post(
        f"https://{region}-aiplatform.googleapis.com/v1beta1/{engine}:streamQuery",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "class_method": "stream_query",
            "input": {"user_id": "deny-test", "message": message},
        },
        timeout=180,
    )


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("deny_test: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    safety = json.loads(Path(".deploy/safety_agent.json").read_text(encoding="utf-8-sig"))
    letters = json.loads(Path(".deploy/letters_agent.json").read_text(encoding="utf-8-sig"))

    # POSITIVE: coordinator identity -> safety engine (granted).
    caseflow_token = _impersonated_token(f"sa-caseflow@{project}.iam.gserviceaccount.com")
    positive = _query(
        safety["resource_name"],
        region,
        caseflow_token,
        json.dumps(
            {
                "applicant_name": "Deny Test",
                "applicant_email": "deny@example.test",
                "permit_type": "accessory_structure",
                "project_description": "install a small garden shed",
                "property_address": "1 Test Way (synthetic)",
                "missing_items": [],
                "complete": True,
            }
        ),
    )
    positive_ok = positive.status_code == 200
    print(
        f"deny_test: POSITIVE caseflow->safety: HTTP {positive.status_code} "
        f"({'PASS' if positive_ok else 'FAIL'})"
    )

    # NEGATIVE: specialist identity -> letters engine (no grant; must be 403).
    safety_token = _impersonated_token(f"sa-safety@{project}.iam.gserviceaccount.com")
    negative = _query(letters["resource_name"], region, safety_token, "{}")
    negative_denied = negative.status_code == 403
    print(
        f"deny_test: NEGATIVE safety->letters: HTTP {negative.status_code} "
        f"({'PASS - denied' if negative_denied else 'FAIL - was not denied!'})"
    )

    # AUDIT: the denial must be in the Data Access audit log (may lag).
    audit_found = False
    audit_entry: dict[str, Any] = {}
    if negative_denied:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default()
        session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
        sa = f"sa-safety@{project}.iam.gserviceaccount.com"
        log_filter = (
            f'logName="projects/{project}/logs/cloudaudit.googleapis.com%2Fdata_access" '
            f'protoPayload.authenticationInfo.principalEmail="{sa}" '
            "protoPayload.status.code=7"
        )
        for _attempt in range(12):
            response = session.post(
                "https://logging.googleapis.com/v2/entries:list",
                json={
                    "resourceNames": [f"projects/{project}"],
                    "filter": log_filter,
                    "orderBy": "timestamp desc",
                    "pageSize": 3,
                },
            )
            entries = response.json().get("entries", [])
            if entries:
                audit_found = True
                audit_entry = entries[0]
                break
            time.sleep(15)
        status = "PASS" if audit_found else "FAIL - no audit entry after 3 min"
        print(f"deny_test: AUDIT entry for the denial: {status}")
        if audit_found:
            payload = audit_entry.get("protoPayload", {})
            print(
                "deny_test: audit evidence: "
                f"principal={payload.get('authenticationInfo', {}).get('principalEmail')} "
                f"method={payload.get('methodName')} "
                f"resource={payload.get('resourceName', '')[-60:]} "
                f"code=PERMISSION_DENIED ts={audit_entry.get('timestamp')}"
            )

    all_pass = positive_ok and negative_denied and audit_found
    print(f"deny_test: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
