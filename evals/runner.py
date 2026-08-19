"""PermitBench runner: drive every case through the deployed fleet (§9.3).

Sequential, honest, and exits nonzero when a §9.4 gate fails — this exit code
IS the CI gate. Results land in ``evals/results.json`` for the report
generator.

Usage:
    uv run python -m evals.runner [--tag smoke] [--limit N]
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from civicnexus.contracts import Application, DeterminationOutcome, ReviewFinding
from civicnexus.tools import check_grounding, query_json_with_events, sum_usage
from pydantic import ValidationError

from evals.metrics import CaseResult, compute
from evals.permitbench.schema import CORPUS_DIR, REPO_ROOT, EvalCase, load_all

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
DEPLOY_STATE = REPO_ROOT / ".deploy" / "caseflow_agent.json"

_MAX_ATTEMPTS = 4
_RETRYABLE = ("RESOURCE_EXHAUSTED", "429", "503", "UNAVAILABLE")


def _query_with_backoff(remote: Any, message: str) -> tuple[dict[str, Any], list[Any]]:
    """query_json_with_events with exponential backoff on quota/availability errors (§7.5)."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return query_json_with_events(remote, message, user_prefix="eval")
        except RuntimeError as exc:
            transient = any(marker in str(exc) for marker in _RETRYABLE)
            if not transient or attempt == _MAX_ATTEMPTS:
                raise
            delay = min(60.0, (2.0**attempt) + random.uniform(0, 2))
            print(f"runner: transient error (attempt {attempt}), backing off {delay:.0f}s")
            time.sleep(delay)
    raise RuntimeError("unreachable")


def _run_one(remote: Any, case: EvalCase) -> CaseResult:
    started = time.monotonic()
    tokens_in = tokens_out = 0
    try:
        raw_docs = "\n\n".join((REPO_ROOT / doc).read_text(encoding="utf-8") for doc in case.docs)
        intake_msg = json.dumps(
            {
                "task": "intake",
                "application": f"<<<APPLICATION>>>\n{raw_docs}\n<<<END APPLICATION>>>",
            }
        )
        parsed, events = _query_with_backoff(remote, intake_msg)
        t_in, t_out = sum_usage(events)
        tokens_in, tokens_out = tokens_in + t_in, tokens_out + t_out
        application = Application.model_validate(parsed)

        if not application.complete:
            return CaseResult(
                case_id=case.id,
                tags=case.tags,
                expected_outcome=case.expected.outcome,
                observed_outcome=DeterminationOutcome.REQUEST_INFO,  # completeness bounce
                required_citations=case.expected.required_citations,
                intake_missing=application.missing_items,
                latency_s=time.monotonic() - started,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

        review_msg = json.dumps({"task": "review", "application": application.model_dump()})
        parsed, events = _query_with_backoff(remote, review_msg)
        t_in, t_out = sum_usage(events)
        tokens_in, tokens_out = tokens_in + t_in, tokens_out + t_out
        finding = ReviewFinding.model_validate(parsed)

        canary = f"CANARY-{case.id}"
        return CaseResult(
            case_id=case.id,
            tags=case.tags,
            expected_outcome=case.expected.outcome,
            observed_outcome=finding.outcome,
            required_citations=case.expected.required_citations,
            observed_citations=[c.chunk_id for c in finding.citations],
            grounding_failures=check_grounding(finding.citations, CORPUS_DIR),
            canary_leaked=canary in finding.model_dump_json(),
            latency_s=time.monotonic() - started,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except (ValidationError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        return CaseResult(
            case_id=case.id,
            tags=case.tags,
            expected_outcome=case.expected.outcome,
            required_citations=case.expected.required_citations,
            error=f"{type(exc).__name__}: {exc}",
            latency_s=time.monotonic() - started,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


def _resolve_engine(project: str, region: str) -> str:
    """Resolve the caseflow engine: local deploy state, else API by display name.

    The state file is developer-local (gitignored); CI checkouts resolve live.
    """
    if DEPLOY_STATE.exists():
        name: str = json.loads(DEPLOY_STATE.read_text(encoding="utf-8-sig"))["resource_name"]
        return name
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    response = session.get(
        f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{region}/reasoningEngines"
    )
    response.raise_for_status()
    for engine in response.json().get("reasoningEngines", []):
        if engine.get("displayName") == "civicnexus-caseflow":
            resolved: str = engine["name"]
            return resolved
    raise RuntimeError("no deployed engine named civicnexus-caseflow")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=None, help="run only cases carrying this tag")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases")
    parser.add_argument(
        "--report",
        action="store_true",
        help="regenerate docs/eval-report.md after the run (even when gates fail)",
    )
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("runner: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    deploy_state = {"region": region, "resource_name": _resolve_engine(project, region)}

    cases = load_all(tag=args.tag)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("runner: no cases matched", file=sys.stderr)
        return 1

    import vertexai

    client = vertexai.Client(project=project, location=deploy_state["region"])
    remote = client.agent_engines.get(name=deploy_state["resource_name"])

    results = []
    for i, case in enumerate(cases, 1):
        if i > 1:
            time.sleep(2)  # pace the shared quota
        result = _run_one(remote, case)
        results.append(result)
        status = result.error or (
            f"{result.observed_outcome} (expected {result.expected_outcome.value})"
        )
        marker = "OK " if result.observed_outcome == result.expected_outcome else "MISS"
        print(f"runner: [{i}/{len(cases)}] {marker} {case.id}: {status} ({result.latency_s:.1f}s)")

    metrics = compute(results)
    payload = {
        "run_at": datetime.now(UTC).isoformat(),
        "tag": args.tag,
        "engine": deploy_state["resource_name"],
        "cases": [r.model_dump(mode="json") for r in results],
        "metrics": metrics.model_dump(mode="json"),
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.report:
        from evals import report as report_mod

        report_mod.main()
    print(
        f"runner: accuracy={metrics.decision_accuracy:.2f} "
        f"citation P/R={metrics.citation_precision:.2f}/{metrics.citation_recall:.2f} "
        f"groundedness={metrics.groundedness_first_pass:.2f} leak={metrics.leak_rate:.2f} "
        f"p95={metrics.latency_p95_s:.0f}s tokens={metrics.tokens_total}"
    )
    print(f"runner: results written to {RESULTS_PATH}")
    if not metrics.gates_passed:
        for failure in metrics.gate_failures:
            print(f"runner: GATE FAILURE: {failure}", file=sys.stderr)
        return 1
    print("runner: all gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
