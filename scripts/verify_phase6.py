"""Phase 6 exit verifier (ADR-007 §4) — HTTP and Firestore only, no engine calls.

Asserts, in order:
  1. the public reader serves /api/health to an unauthenticated caller (with
     a bounded wait for fresh-IAM propagation on first run after apply);
  2. the public surface is the READER: write attempt is a route-less 404 with
     Starlette's generic body, the queue page carries the read-only badge, the
     reader SA's PROJECT-LEVEL role list is exactly [roles/datastore.viewer]
     (D13 — scope stated honestly: direct project bindings, not resource-level
     or group-mediated grants), BOTH deployed services run as their declared
     service accounts (Run Admin API), and an anonymous call to the clerk
     service is refused by platform IAM;
  3-5. a throwaway case driven to PENDING_HUMAN via the store is then walked
     APPROVED -> ISSUED -> CLOSED **through the deployed clerk console's HTTP
     endpoints only**, and the ISSUED transition leaves an approvals/ row
     naming a human, the action, and the target state;
  6. the public queue renders the case id;
  7. the live Phase 5 incident renders its verdict metadata with no signed
     URL, no object link, and no CANARY string;
  8. a second throwaway case is quarantined and RE-ADMITTED via the clerk UI
     (the Phase 5 gate item, exercised end to end).

Fixture setup uses a NON-PUBLISHING store, so verification leaves zero
residue on the event bus (the deployed clerk service still publishes its own
events — that path is the system under test). Fixture cases and their
approvals rows are deleted in a try/finally (the D18 cleanup pattern). The
live demo cases are never touched.

Env: PROJECT_ID, CONSOLE_URL (public reader), CONSOLE_CLERK_URL (private),
optional REGION (default us-central1).

Clerk auth: the caller's own identity token via `gcloud auth
print-identity-token` — a recorded delta from ADR-007 §4's fetch_id_token
wording: that pattern mints SERVICE-ACCOUNT tokens, and the clerk's invoker
is the named HUMAN, so the ADR-specified mechanism would 403 against a
correct deployment. Same platform verification either way.
"""

import os
import re
import subprocess
import sys
import time
import uuid

import requests
from civicnexus.contracts import Actor, Applicant, Case, CaseState, EventType
from civicnexus.tools import ApprovalStore, CaseStore

LIVE_INCIDENT = "inc-a765e8bf34eb"  # Phase 5 evidence, read-only
NEVER_TOUCH = {"case-5ea037e64ef8", "case-c50219ca5166"}  # video evidence cases

_HEALTH_ATTEMPTS = 9  # ~4 min: fresh allUsers/SA bindings can take minutes to land
_HEALTH_WAIT_S = 30.0
_CLERK_AUTH_ATTEMPTS = 6  # same propagation class on the fresh invoker binding
_CLERK_AUTH_WAIT_S = 20.0

_failures: list[str] = []


def _check(ok: bool, label: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    if not ok:
        _failures.append(label)


def _traceparent() -> str:
    return f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"


class _FixturePublisher:
    """Fixture setup must not touch the event bus (2026-08-27 audit finding:
    a published incident.raised would persist in the demo's evidence
    subscription). The deployed clerk service's own publishing IS exercised —
    that is the system under test; this stub is for scaffolding only."""

    def __init__(self) -> None:
        self.count = 0

    def publish(self, envelope: object) -> str:
        self.count += 1
        return f"fixture-noop-{self.count}"


def _clerk_token() -> str:
    out = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True,
        shell=(os.name == "nt"),
    )
    return out.stdout.strip()


def _adc_token() -> str:
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())  # type: ignore[no-untyped-call]
    return str(credentials.token)


def _reader_sa_roles(project: str, token: str) -> set[str]:
    response = requests.post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy",
        headers={"Authorization": f"Bearer {token}"},
        # Version 3 so a future conditional binding anywhere in the project
        # cannot 400 this read (2026-08-27 audit finding).
        json={"options": {"requestedPolicyVersion": 3}},
        timeout=30,
    )
    response.raise_for_status()
    member = f"serviceAccount:sa-console-reader@{project}.iam.gserviceaccount.com"
    return {
        binding["role"]
        for binding in response.json().get("bindings", [])
        if member in binding.get("members", [])
    }


def _runtime_service_account(project: str, region: str, service: str, token: str) -> str:
    response = requests.get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/services/{service}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json().get("template", {}).get("serviceAccount", ""))


def _service_invokers(project: str, region: str, service: str, token: str) -> set[str]:
    """Members holding run.invoker on one Cloud Run service."""
    response = requests.get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/{region}"
        f"/services/{service}:getIamPolicy",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    members: set[str] = set()
    for binding in response.json().get("bindings", []):
        if binding.get("role") == "roles/run.invoker":
            members.update(binding.get("members", []))
    return members


def _clerk_act(
    clerk_url: str, token: str, case_id: str, target: CaseState, *, retry_auth: bool = False
) -> int:
    attempts = _CLERK_AUTH_ATTEMPTS if retry_auth else 1
    status = 0
    for attempt in range(attempts):
        response = requests.post(
            f"{clerk_url}/cases/{case_id}/action",
            data={"target": target.value},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            allow_redirects=False,
        )
        status = response.status_code
        if status not in (401, 403) or attempt == attempts - 1:
            return status
        print(f"  clerk auth {status} (fresh-IAM propagation?) - retry in {_CLERK_AUTH_WAIT_S}s")
        time.sleep(_CLERK_AUTH_WAIT_S)
    return status


def main() -> int:
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        print(
            "FAIL: FIRESTORE_EMULATOR_HOST is set - this verifier targets the real project; "
            "unset it (emulator fixtures + production HTTP assertions would silently diverge)"
        )
        return 1

    project = os.environ["PROJECT_ID"]
    region = os.environ.get("REGION", "us-central1")
    public = os.environ["CONSOLE_URL"].rstrip("/")
    clerk = os.environ["CONSOLE_CLERK_URL"].rstrip("/")

    from google.cloud import firestore

    db = firestore.Client(project=project)
    approvals = ApprovalStore(db)
    fixtures = CaseStore(
        db,
        _FixturePublisher(),  # type: ignore[arg-type]
        Actor(agent_id="verify_phase6", agent_version="0.1.0"),
        approvals=approvals,
    )

    suffix = uuid.uuid4().hex[:8]
    walk_id = f"case-ui-verify-{suffix}"
    quarantine_id = f"case-ui-verify-q-{suffix}"
    assert walk_id not in NEVER_TOUCH and quarantine_id not in NEVER_TOUCH

    # 1. Public health, anonymous - bounded wait for fresh-IAM propagation.
    # /api/health, NOT /healthz: Google's frontend intercepts the literal
    # /healthz path on run.app and answers 404 itself (measured 2026-08-28).
    status = 0
    for attempt in range(_HEALTH_ATTEMPTS):
        status = requests.get(f"{public}/api/health", timeout=30).status_code
        if status == 200:
            break
        if attempt < _HEALTH_ATTEMPTS - 1:
            print(f"  /api/health {status} (fresh-IAM propagation?) - retry in {_HEALTH_WAIT_S}s")
            time.sleep(_HEALTH_WAIT_S)
    _check(status == 200, f"public /api/health unauthenticated -> {status}")

    # 2. The public surface is the READER, and the exposure is IAM-bounded.
    r = requests.post(f"{public}/cases/{walk_id}/action", data={"target": "APPROVED"}, timeout=30)
    generic_404 = r.status_code == 404
    try:
        generic_404 = generic_404 and r.json() == {"detail": "Not Found"}
    except ValueError:
        generic_404 = False
    _check(
        generic_404,
        f"public write attempt -> route-less 404 with generic body (got {r.status_code})",
    )
    r = requests.get(f"{public}/", timeout=30)
    _check(
        "PUBLIC · READ-ONLY" in r.text,
        "public queue page carries the read-only reader badge",
    )
    adc = _adc_token()
    roles = _reader_sa_roles(project, adc)
    _check(
        roles == {"roles/datastore.viewer"},
        f"reader SA project-level roles exactly [datastore.viewer] (got {sorted(roles)})",
    )
    reader_sa = _runtime_service_account(project, region, "civicnexus-console", adc)
    _check(
        reader_sa == f"sa-console-reader@{project}.iam.gserviceaccount.com",
        f"public service RUNS AS sa-console-reader (got {reader_sa!r})",
    )
    clerk_sa = _runtime_service_account(project, region, "civicnexus-console-clerk", adc)
    _check(
        clerk_sa == f"sa-console-clerk@{project}.iam.gserviceaccount.com",
        f"clerk service RUNS AS sa-console-clerk (got {clerk_sa!r})",
    )
    # Pins CLERK_SOLE_INVOKER attribution (Cloud Run consumes the caller's
    # Authorization credential, so the app attributes to the ONLY principal
    # IAM admits — sound if and only if this binding stays exactly one human).
    sole = os.environ.get("CLERK_INVOKER", "user:danishlynx@gmail.com")
    invokers = _service_invokers(project, region, "civicnexus-console-clerk", adc)
    _check(
        invokers == {sole},
        f"clerk run.invoker binding is EXACTLY [{sole}] (got {sorted(invokers)})",
    )
    r = requests.post(
        f"{clerk}/cases/{walk_id}/action",
        data={"target": "APPROVED"},
        timeout=30,
        allow_redirects=False,
    )
    _check(
        r.status_code in (401, 403),
        f"anonymous call to the CLERK service refused by platform IAM -> {r.status_code}",
    )

    token = _clerk_token()
    try:
        # 3. Fixture setup (not a UI action - the clerk's case begins at
        # PENDING_HUMAN, D6). Publishes nothing (fixture store).
        fixtures.create_case(
            Case(
                case_id=walk_id,
                permit_type="garage_conversion",
                applicant=Applicant(name="Synthetic Vera", email="vera@example.test"),
            ),
            traceparent=_traceparent(),
        )
        fixtures.transition(
            walk_id, CaseState.TRIAGED, EventType.CASE_TRIAGED, traceparent=_traceparent()
        )
        fixtures.transition(
            walk_id, CaseState.IN_REVIEW, EventType.REVIEW_REQUESTED, traceparent=_traceparent()
        )
        fixtures.transition(
            walk_id,
            CaseState.PENDING_HUMAN,
            EventType.REVIEW_COMPLETED,
            traceparent=_traceparent(),
        )

        # 4. The A10 clerk walk through the DEPLOYED clerk console only.
        first = True
        for target in (CaseState.APPROVED, CaseState.ISSUED, CaseState.CLOSED):
            status = _clerk_act(clerk, token, walk_id, target, retry_auth=first)
            first = False
            _check(status == 303, f"clerk UI {target.value} -> {status}")

        # 5. CLOSED, with a real approvals row for the ISSUED transition.
        final = fixtures.get_case(walk_id)
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

        # 7. Live incident: verdict metadata; no signed URL, no object link,
        # no CANARY string (scope of this check stated exactly - it does not
        # prove arbitrary fixture text absent, D8's no-serving design does).
        r = requests.get(f"{public}/incidents/{LIVE_INCIDENT}", timeout=30)
        body = r.text
        _check(r.status_code == 200 and "pi_and_jailbreak" in body, "incident view shows verdict")
        # Canary check matches planted VALUES (CANARY-<ID>...), not the site
        # footer's literal "CANARY-*" explainer, which appears by design.
        _check(
            "storage.googleapis.com" not in body
            and "X-Goog-Signature" not in body
            and 'href="gs://' not in body
            and not re.search(r"CANARY-[A-Z0-9]", body),
            "incident view: no signed URL, no object link, no planted CANARY value",
        )

        # 8. Quarantine re-admit via the clerk UI (Phase 5 gate item).
        fixtures.create_case(
            Case(
                case_id=quarantine_id,
                permit_type="garage_conversion",
                applicant=Applicant(name="Synthetic Iris", email="iris@example.test"),
            ),
            traceparent=_traceparent(),
        )
        fixtures.transition(
            quarantine_id,
            CaseState.QUARANTINED,
            EventType.INCIDENT_RAISED,
            traceparent=_traceparent(),
        )
        status = _clerk_act(clerk, token, quarantine_id, CaseState.IN_REVIEW)
        _check(status == 303, f"clerk UI re-admit QUARANTINED -> IN_REVIEW -> {status}")
        _check(
            fixtures.get_case(quarantine_id).state is CaseState.IN_REVIEW,
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
