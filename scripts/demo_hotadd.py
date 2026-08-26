"""Demo moment 1 (§12): hot-add a new specialist mid-run, no redeploys.

The scripted, repeatable sequence the video shows live:
1. BEFORE: a case requiring tree_preservation runs — the coordinator honestly
   reports the capability has no approved specialist.
2. The tree-preservation agent deploys under its own identity (sa-treepres)
   and is REGISTERED in the registry — status PENDING. Still not dispatchable:
   pending is not approved (tool-poisoning defense).
3. THE HUMAN approves the card (named actor, audited).
4. The access matrix adds sa-caseflow -> treepres engine (engine_iam).
5. AFTER: the same case runs again — the coordinator's registry toolset now
   builds consult_tree_preservation and routes to it. Nothing redeployed.

Requires: REGISTRY_URL routable, caseflow rebound with REGISTRY_URL — OR the
B-007 interim: REGISTRY_MODE=firestore (here and on the caseflow engine), in
which case register/approve go through the RegistryStore library under the
human's ADC identity (same lifecycle, same guards; see ADR-003 addendum).
Each full run deploys/uses billable resources — run only with the human's OK.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

TREEPRES_STATE = Path(".deploy/treepres_agent.json")
CASEFLOW_STATE = Path(".deploy/caseflow_agent.json")
CARD_VERSION = "1.0.0"

DEMO_APPLICATION = {
    "applicant_name": "Synthetic Rosa",
    "applicant_email": "rosa@example.test",
    "permit_type": "garage_conversion",
    "project_description": (
        "Convert the detached garage to a home office; the driveway extension "
        "requires removing one mature oak tree near the property line."
    ),
    "property_address": "77 Demo Grove (synthetic)",
    "missing_items": [],
    "complete": True,
}


def _registry(method: str, path: str, body: dict[str, Any] | None = None) -> requests.Response:
    import google.auth.transport.requests
    from google.oauth2 import id_token as id_token_mod

    base = os.environ["REGISTRY_URL"].rstrip("/")
    token = id_token_mod.fetch_id_token(  # type: ignore[no-untyped-call]
        google.auth.transport.requests.Request(), base
    )
    return requests.request(
        method,
        f"{base}{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _firestore_mode() -> bool:
    return os.environ.get("REGISTRY_MODE", "http") == "firestore"


def _register_and_approve_firestore(endpoint: str, approver: str) -> None:
    """B-007 interim: same lifecycle, same guards, via the store library.

    The human's ADC identity performs both actions; the approval names the
    approver exactly as the HTTP path would.
    """
    from civicnexus.contracts import AgentCard, AgentStatus
    from google.cloud import firestore
    from registry.store import DuplicateCardError, RegistryStore

    store = RegistryStore(firestore.Client(project=os.environ.get("PROJECT_ID")))
    card = AgentCard(
        agent_id="tree-preservation",
        version=CARD_VERSION,
        display_name="Tree preservation reviewer",
        description="Reviews applications for impact on protected trees and landscaping.",
        capabilities=["tree_preservation"],
        endpoint=endpoint,
    )
    try:
        store.register(card)
        print(f"demo_hotadd: registered tree-preservation@{CARD_VERSION} (PENDING)")
    except DuplicateCardError:
        print(f"demo_hotadd: tree-preservation@{CARD_VERSION} already registered (re-run)")
    current = store.get("tree-preservation", CARD_VERSION)
    if current.status is not AgentStatus.APPROVED:
        store.change_status(
            "tree-preservation",
            CARD_VERSION,
            AgentStatus.APPROVED,
            actor=approver,
            human_actor=True,
        )
    print(f"demo_hotadd: APPROVED by {approver}")


def _review(message_extra: dict[str, Any], label: str) -> dict[str, Any]:
    """ADR-005 §3.3/§6: bounded retry ONLY on pre-first-event failures
    (connection/503 before any stream output — mid-stream failures are
    ambiguous and never retried); every reply/failure persisted with
    timings so no diagnosis ever needs engine logs again."""
    import time

    import vertexai
    from civicnexus.tools import query_json

    state = json.loads(CASEFLOW_STATE.read_text(encoding="utf-8-sig"))
    client = vertexai.Client(project=state["project"], location=state["region"])
    remote = client.agent_engines.get(name=state["resource_name"])
    payload = {
        "task": "review",
        "application": DEMO_APPLICATION,
        "capabilities": ["zoning", "tree_preservation"],
    }
    payload.update(message_extra)
    record: dict[str, Any] = {"label": label, "attempts": []}
    try:
        for attempt in (1, 2):
            started = time.monotonic()
            try:
                reply = query_json(remote, json.dumps(payload), user_prefix="hotadd")
                record["attempts"].append(
                    {"n": attempt, "seconds": round(time.monotonic() - started, 1), "ok": True}
                )
                record["reply"] = reply
                return reply
            except Exception as exc:
                elapsed = time.monotonic() - started
                message = f"{type(exc).__name__}: {exc}"
                # "no text" / stream errors after events flowed = mid-stream;
                # fast connection-level failures = pre-first-event.
                pre_first_event = elapsed < 15 or "503" in message
                record["attempts"].append(
                    {
                        "n": attempt,
                        "seconds": round(elapsed, 1),
                        "ok": False,
                        "error": message[:500],
                        "retried": pre_first_event and attempt == 1,
                    }
                )
                if not (pre_first_event and attempt == 1):
                    raise
                time.sleep(30)
        raise RuntimeError("unreachable")
    finally:
        log_path = Path(".deploy/demo_last_run.json")
        log_path.parent.mkdir(exist_ok=True)
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8-sig"))
            except Exception:
                existing = []
        existing.append(record)
        log_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


def _tree_finding_present(reply: dict[str, Any]) -> tuple[bool, str]:
    """ADR-005 amendment 5: structured assert — a contained error envelope
    containing the word 'tree' must NOT pass. Requires a tree_preservation
    finding with non-empty citations and no error, and no missing_capability."""
    if "missing_capability" in json.dumps(reply):
        return False, "reply still reports missing_capability"
    findings = reply.get("findings")
    if not isinstance(findings, list):
        return False, "reply has no findings envelope"
    for entry in findings:
        if not isinstance(entry, dict) or entry.get("capability") != "tree_preservation":
            continue
        finding = entry.get("finding")
        if not isinstance(finding, dict) or "error" in finding:
            return False, f"tree_preservation entry is an error/invalid: {str(finding)[:120]}"
        citations = finding.get("citations")
        if not isinstance(citations, list) or not citations:
            return False, "tree_preservation finding has no citations"
        return True, f"outcome={finding.get('outcome')} citations={len(citations)}"
    return False, "no tree_preservation entry in findings"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approver", required=True, help="the human's email, recorded as the approving actor"
    )
    parser.add_argument("--skip-deploy", action="store_true", help="treepres already deployed")
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID")
    if not project or (not _firestore_mode() and not os.environ.get("REGISTRY_URL")):
        print(
            "demo_hotadd: PROJECT_ID required; REGISTRY_URL required unless "
            "REGISTRY_MODE=firestore",
            file=sys.stderr,
        )
        return 1

    # 1. BEFORE: capability has no approved specialist.
    before = _review({}, "BEFORE")
    before_text = json.dumps(before)
    print(
        f"demo_hotadd: BEFORE - coordinator reply mentions missing capability: "
        f"{'missing_capability' in before_text}"
    )

    # 2. Deploy + register (PENDING).
    if not args.skip_deploy:
        deploy = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/deploy_agent.py",
                "--agent-dir",
                "agents/treepres/src/treepres_agent",
                "--display-name",
                "civicnexus-treepres",
                "--service-account",
                "sa-treepres",
                "--needs-corpus",
                "--state-file",
                str(TREEPRES_STATE),
            ],
            timeout=1200,
        )
        if deploy.returncode != 0:
            print("demo_hotadd: treepres deploy failed", file=sys.stderr)
            return 1
    endpoint = json.loads(TREEPRES_STATE.read_text(encoding="utf-8-sig"))["resource_name"]

    if _firestore_mode():
        # 2b+3. Register (PENDING) then human approval, via the store library.
        _register_and_approve_firestore(endpoint, args.approver)
    else:
        register = _registry(
            "POST",
            "/agents",
            {
                "agent_id": "tree-preservation",
                "version": CARD_VERSION,
                "display_name": "Tree preservation reviewer",
                "description": (
                    "Reviews applications for impact on protected trees and landscaping."
                ),
                "capabilities": ["tree_preservation"],
                "endpoint": endpoint,
            },
        )
        if register.status_code not in (201, 409):  # 409 = already registered (re-run)
            print(f"demo_hotadd: registration failed: {register.status_code} {register.text}")
            return 1
        print(f"demo_hotadd: registered tree-preservation@{CARD_VERSION} (PENDING)")

        # 3. THE HUMAN approves — the moment the demo pivots on.
        approve = _registry(
            "POST",
            f"/agents/tree-preservation/{CARD_VERSION}/approve",
            {"actor": args.approver, "human_actor": True},
        )
        if approve.status_code != 200:
            print(f"demo_hotadd: approval failed: {approve.status_code} {approve.text}")
            return 1
        print(f"demo_hotadd: APPROVED by {args.approver}")

    # 4. Access matrix: coordinator may now consult the new engine.
    matrix = subprocess.run(
        ["uv", "run", "python", "scripts/engine_iam.py"],
        env={**os.environ, "HOTADD_EXTRA": str(TREEPRES_STATE)},
        timeout=300,
    )
    if matrix.returncode != 0:
        print("demo_hotadd: engine IAM update failed", file=sys.stderr)
        return 1

    # 5. AFTER: same case, rerun — the new specialist answers.
    after = _review({}, "AFTER")
    routed, detail = _tree_finding_present(after)
    print(f"demo_hotadd: AFTER - tree-preservation finding present: {routed} ({detail})")
    print("demo_hotadd: " + ("PASS - hot-add complete, nothing redeployed" if routed else "FAIL"))
    return 0 if routed else 1


if __name__ == "__main__":
    raise SystemExit(main())
