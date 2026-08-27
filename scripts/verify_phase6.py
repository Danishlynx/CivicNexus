"""Phase 6 exit verifier (ADR-007 §4) — $0: HTTP and Firestore only, no engine calls.

Asserts, in order:
  1. the public reader serves /healthz to an unauthenticated caller;
  2. a write attempt on the public service is a 404 (routes not mounted), and
     the reader SA's project role list is EXACTLY [roles/datastore.viewer] (D13);
  3-5. a throwaway case driven to PENDING_HUMAN via the store is then walked
     APPROVED -> ISSUED -> CLOSED **through the deployed clerk console's HTTP
     endpoints only**, and the ISSUED transition leaves an approvals/ row
     naming a human, the action, and the target state;
  6. the public queue renders the case id;
  7. the live Phase 5 incident renders metadata with no signed URL and no bytes;
  8. a second throwaway case is quarantined and RE-ADMITTED via the clerk UI
     (the Phase 5 gate item, exercised end to end).

Fixture cases and their approvals rows are deleted in a try/finally (the D18
cleanup pattern). The live demo cases are never touched.

Env: PROJECT_ID, CONSOLE_URL (public reader), CONSOLE_CLERK_URL (private).
Clerk auth: the caller's own identity token (`gcloud auth print-identity-token`),
i.e. the same named human the clerk service's IAM admits.
"""

import os
import subprocess
import sys
import uuid

import requests
from civicnexus.contracts import Actor, Applicant, Case, CaseState, EventType
from civicnexus.tools import ApprovalStore, CaseStore, EventPublisher

LIVE_INCIDENT = "inc-a765e8bf34eb"  # Phase 5 evidence, read-only
NEVER_TOUCH = {"case-5ea037e64ef8", "case-c50219ca5166"}  # video evidence cases

_failures: list[str] = []


def _check(ok: bool, label: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    if not ok:
        _failures.append(label)


def _traceparent() -> str:
    return f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"


def _clerk_token() -> str:
    out = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True,
        shell=(os.name == "nt"),
    )
    return out.stdout.strip()


def _reader_sa_roles(project: str) -> set[str]:
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())  # type: ignore[no-untyped-call]
    response = requests.post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy",
        headers={"Authorization": f"Bearer {credentials.token}"},
        json={},
        timeout=30,
    )
    response.raise_for_status()
    member = f"serviceAccount:sa-console-reader@{project}.iam.gserviceaccount.com"
    return {
        binding["role"]
        for binding in response.json().get("bindings", [])
        if member in binding.get("members", [])
    }


def _clerk_act(clerk_url: str, token: str, case_id: str, target: CaseState) -> int:
    response = requests.post(
        f"{clerk_url}/cases/{case_id}/action",
        data={"target": target.value},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        allow_redirects=False,
    )
    return response.status_code


def main() -> int:
    project = os.environ["PROJECT_ID"]
    public = os.environ["CONSOLE_URL"].rstrip("/")
    clerk = os.environ["CONSOLE_CLERK_URL"].rstrip("/")

    from google.cloud import firestore

    db = firestore.Client(project=project)
    approvals = ApprovalStore(db)
    store = CaseStore(
        db,
        EventPublisher(project),
        Actor(agent_id="verify_phase6", agent_version="0.1.0"),
        approvals=approvals,
    )

    suffix = uuid.uuid4().hex[:8]
    walk_id = f"case-ui-verify-{suffix}"
    quarantine_id = f"case-ui-verify-q-{suffix}"
    assert walk_id not in NEVER_TOUCH and quarantine_id not in NEVER_TOUCH

    # 1. Public health, anonymous.
    r = requests.get(f"{public}/healthz", timeout=30)
    _check(r.status_code == 200, f"public /healthz unauthenticated -> {r.status_code}")

    # 2. Public write attempt is a 404; reader SA holds exactly datastore.viewer.
    r = requests.post(f"{public}/cases/{walk_id}/action", data={"target": "APPROVED"}, timeout=30)
    _check(r.status_code == 404, f"public write attempt -> {r.status_code} (routes not mounted)")
    roles = _reader_sa_roles(project)
    _check(
        roles == {"roles/datastore.viewer"},
        f"reader SA project roles exactly [datastore.viewer] (got {sorted(roles)})",
    )

    token = _clerk_token()
    try:
        # 3. Fixture setup (not a UI action - the clerk's case begins at
        # PENDING_HUMAN, D6).
        store.create_case(
            Case(
                case_id=walk_id,
                permit_type="garage_conversion",
                applicant=Applicant(name="Synthetic Vera", email="vera@example.test"),
            ),
            traceparent=_traceparent(),
        )
        store.transition(
            walk_id, CaseState.TRIAGED, EventType.CASE_TRIAGED, traceparent=_traceparent()
        )
        store.transition(
            walk_id, CaseState.IN_REVIEW, EventType.REVIEW_REQUESTED, traceparent=_traceparent()
        )
        store.transition(
            walk_id,
            CaseState.PENDING_HUMAN,
            EventType.REVIEW_COMPLETED,
            traceparent=_traceparent(),
        )

        # 4. The A10 clerk walk through the DEPLOYED clerk console only.
        for target in (CaseState.APPROVED, CaseState.ISSUED, CaseState.CLOSED):
            status = _clerk_act(clerk, token, walk_id, target)
            _check(status == 303, f"clerk UI {target.value} -> {status}")

        # 5. CLOSED, with a real approvals row for the ISSUED transition.
        final = store.get_case(walk_id)
        _check(final.state is CaseState.CLOSED, f"case ends {final.state.value}")
        rows = [
            approvals.get(snapshot.id)
            for snapshot in db.collection("approvals").where("case_id", "==", walk_id).stream()
        ]
        issued = [row for row in rows if row.target_state is CaseState.ISSUED]
        _check(
            bool(issued) and bool(issued[0].approver) and issued[0].action == "issue",
            "approvals/ row names a human, the action, and ISSUED "
            + (f"(approver={issued[0].approver})" if issued else "(no row found)"),
        )

        # 6. The public queue renders the case id.
        r = requests.get(f"{public}/", timeout=30)
        _check(walk_id in r.text, "public queue renders the fixture case id")

        # 7. Live incident: metadata only, no signed URL, no quarantined bytes.
        r = requests.get(f"{public}/incidents/{LIVE_INCIDENT}", timeout=30)
        body = r.text
        _check(r.status_code == 200 and "pi_and_jailbreak" in body, "incident view shows verdict")
        _check(
            "storage.googleapis.com" not in body
            and "X-Goog-Signature" not in body
            and 'href="gs://' not in body,
            "incident view carries no signed URL and no object link",
        )

        # 8. Quarantine re-admit via the clerk UI (Phase 5 gate item).
        store.create_case(
            Case(
                case_id=quarantine_id,
                permit_type="garage_conversion",
                applicant=Applicant(name="Synthetic Iris", email="iris@example.test"),
            ),
            traceparent=_traceparent(),
        )
        store.transition(
            quarantine_id,
            CaseState.QUARANTINED,
            EventType.INCIDENT_RAISED,
            traceparent=_traceparent(),
        )
        status = _clerk_act(clerk, token, quarantine_id, CaseState.IN_REVIEW)
        _check(status == 303, f"clerk UI re-admit QUARANTINED -> IN_REVIEW -> {status}")
        _check(
            store.get_case(quarantine_id).state is CaseState.IN_REVIEW,
            "re-admitted case is IN_REVIEW",
        )
    finally:
        # 9. D18 cleanup: fixture cases and their approvals rows only.
        removed: list[str] = []
        for case_id in (walk_id, quarantine_id):
            doc = db.collection("cases").document(case_id)
            if doc.get().exists:
                doc.delete()
                removed.append(case_id)
            for snapshot in db.collection("approvals").where("case_id", "==", case_id).stream():
                db.collection("approvals").document(snapshot.id).delete()
                removed.append(f"approvals/{snapshot.id}")
        print(f"cleanup removed: {removed}")

    if _failures:
        print(f"verify-phase6: {len(_failures)} FAILED assertion(s)")
        return 1
    print("verify-phase6: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
