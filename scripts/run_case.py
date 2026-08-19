"""Drive one synthetic case end to end — the Phase 1 vertical slice (§11).

RECEIVED → TRIAGED → IN_REVIEW → cited determination → PENDING_HUMAN, against
the real deployed stack: Firestore case store, Pub/Sub events, and the
caseflow agent on Agent Engine. Passing means the Phase 1 exit criterion holds:
the case sits in PENDING_HUMAN carrying a determination whose citations name
real corpus sections and quote them verbatim.
"""

import json
import os
import secrets
import sys
from pathlib import Path

from civicnexus.contracts import (
    Actor,
    Applicant,
    Application,
    Case,
    CaseState,
    EventType,
    ReviewFinding,
)
from civicnexus.contracts.permit_types import load_permit_types
from civicnexus.tools import CaseStore, EventPublisher, query_json
from civicnexus.verifier import verify_finding

STATE_FILE = Path(".deploy/caseflow_agent.json")
FIXTURE = Path("data/fixtures/maria_application.txt")
CORPUS_DIR = Path("data/corpus")
AGENT_VERSION = "0.1.0"


def _traceparent() -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    project = os.environ.get("PROJECT_ID")
    if not project:
        print("run_case: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    if not STATE_FILE.exists():
        print(f"run_case: {STATE_FILE} missing - deploy caseflow first", file=sys.stderr)
        return 1
    deploy_state = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))

    import vertexai
    from google.cloud import firestore

    client = vertexai.Client(project=project, location=deploy_state["region"])
    remote = client.agent_engines.get(name=deploy_state["resource_name"])
    store = CaseStore(
        firestore.Client(project=project),
        EventPublisher(project),
        Actor(agent_id="run_case_driver", agent_version=AGENT_VERSION),
    )

    traceparent = _traceparent()
    case_id = f"case-{secrets.token_hex(6)}"
    raw_application = FIXTURE.read_text(encoding="utf-8")

    # 1. Intake: raw text -> structured application.
    intake_msg = json.dumps(
        {
            "task": "intake",
            "application": f"<<<APPLICATION>>>\n{raw_application}\n<<<END APPLICATION>>>",
        }
    )
    application = Application.model_validate(query_json(remote, intake_msg, user_prefix="run-case"))
    print(
        f"run_case: intake parsed applicant={application.applicant_name!r} "
        f"complete={application.complete} missing={application.missing_items}"
    )

    # 2. Case created (RECEIVED) then triaged.
    store.create_case(
        Case(
            case_id=case_id,
            permit_type=application.permit_type,
            applicant=Applicant(name=application.applicant_name, email=application.applicant_email),
            trace_id=traceparent.split("-")[1],
        ),
        traceparent=traceparent,
    )
    store.transition(
        case_id,
        CaseState.TRIAGED,
        EventType.CASE_TRIAGED,
        traceparent=traceparent,
        payload={"missing_items": application.missing_items},
    )
    if not application.complete:
        store.transition(
            case_id,
            CaseState.INCOMPLETE_AWAITING_APPLICANT,
            EventType.APPLICANT_MESSAGE,
            traceparent=traceparent,
            payload={"missing_items": application.missing_items},
        )
        print(
            f"run_case: case {case_id} awaiting applicant (missing items) - "
            "slice requires a complete application; check the fixture"
        )
        return 1

    # 3. Review: coordinator -> zoning -> cited finding.
    store.transition(
        case_id,
        CaseState.IN_REVIEW,
        EventType.REVIEW_REQUESTED,
        traceparent=traceparent,
        payload={"capabilities": ["zoning"]},
    )
    review_msg = json.dumps({"task": "review", "application": application.model_dump()})
    finding = ReviewFinding.model_validate(query_json(remote, review_msg, user_prefix="run-case"))

    # §7.3 gate: verify; on first failure, VERIFICATION_FAILED round-trip and
    # one retry with the critique; second failure still lands PENDING_HUMAN,
    # report attached, for the clerk to see.
    permit_types = load_permit_types(Path("config/permit_types.yaml"))
    permit_cfg = permit_types.get(application.permit_type)
    allowed = permit_cfg.allowed_outcomes if permit_cfg else []
    report = verify_finding(
        finding,
        application=application.model_dump(),
        permit_allowed_outcomes=allowed,
        corpus_dir=CORPUS_DIR,
    )
    if not report.passed:
        print(f"run_case: verifier FAILED first pass: {report.critique}")
        store.transition(
            case_id,
            CaseState.VERIFICATION_FAILED,
            EventType.VERIFICATION_FAILED,
            traceparent=traceparent,
            payload={"failures": report.failures},
        )
        store.transition(
            case_id,
            CaseState.IN_REVIEW,
            EventType.REVIEW_REQUESTED,
            traceparent=traceparent,
            payload={"retry": True},
        )
        retry_msg = json.dumps(
            {
                "task": "review",
                "application": application.model_dump(),
                "verifier_critique": report.critique or "; ".join(report.failures),
            }
        )
        finding = ReviewFinding.model_validate(
            query_json(remote, retry_msg, user_prefix="run-case")
        )
        report = verify_finding(
            finding,
            application=application.model_dump(),
            permit_allowed_outcomes=allowed,
            corpus_dir=CORPUS_DIR,
        )
    print(f"run_case: verifier {'PASSED' if report.passed else 'failed twice (clerk sees report)'}")

    determination = finding.to_determination(
        agent_id="zoning",
        agent_version=AGENT_VERSION,
        trace_id=traceparent.split("-")[1],
        verifier_report=report.as_payload(),
    )
    store.add_determination(case_id, determination, traceparent=traceparent)

    # 4. Await the human — the Phase 1 finish line.
    final = store.transition(
        case_id,
        CaseState.PENDING_HUMAN,
        EventType.ACTION_PENDING_APPROVAL,
        traceparent=traceparent,
        payload={"determinations": 1},
    )

    canary_leak = "CANARY-P1-MARIA" in json.dumps(finding.model_dump())
    print(f"run_case: outcome={finding.outcome.value} confidence={finding.confidence}")
    for citation in finding.citations:
        print(f"run_case: cited {citation.chunk_id}: {citation.quote[:80]!r}")
    print(f"run_case: final state={final.state.value} case={case_id}")
    if canary_leak:
        print("run_case: WARNING - canary string surfaced in the finding (leak signal)")
    assert final.state is CaseState.PENDING_HUMAN
    print("run_case: PHASE 1 SLICE COMPLETE - cited determination is PENDING_HUMAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
