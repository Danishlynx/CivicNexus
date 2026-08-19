"""Generate docs/eval-report.md from evals/results.json (§9.5).

The report is regenerated whole on every full run — never hand-edited — and
always carries a "where it still fails" section built from the actual misses.
"""

import json
import sys
from pathlib import Path

from evals.metrics import GATES, CaseResult, Metrics
from evals.permitbench.schema import REPO_ROOT

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
REPORT_PATH = REPO_ROOT / "docs" / "eval-report.md"


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"report: {RESULTS_PATH} missing - run the runner first", file=sys.stderr)
        return 1
    payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    metrics = Metrics.model_validate(payload["metrics"])
    cases = [CaseResult.model_validate(c) for c in payload["cases"]]

    lines = [
        "# PermitBench eval report",
        "",
        f"Generated from `evals/results.json` — run at {payload['run_at']}, "
        f"tag `{payload.get('tag') or 'all'}`, {metrics.cases} cases against "
        f"`{payload['engine'].rsplit('/', 1)[-1]}`. Do not hand-edit.",
        "",
        "## Headline metrics",
        "",
        "| Metric | Value | Gate |",
        "|---|---|---|",
        f"| Decision accuracy | {metrics.decision_accuracy:.2%} "
        f"| ≥ {GATES['decision_accuracy']:.0%} |",
        f"| Citation precision | {metrics.citation_precision:.2%} | — |",
        f"| Citation recall | {metrics.citation_recall:.2%} | — |",
        f"| Groundedness first-pass | {metrics.groundedness_first_pass:.2%} "
        f"| ≥ {GATES['groundedness_first_pass']:.0%} |",
        f"| Canary leak rate | {metrics.leak_rate:.2%} | = 0 |",
        f"| Latency p50 / p95 | {metrics.latency_p50_s:.0f}s / {metrics.latency_p95_s:.0f}s | — |",
        f"| Tokens (run total) | {metrics.tokens_total:,} | — |",
        f"| Errors | {metrics.errors} | — |",
        "",
        "**Gates: "
        + ("PASS" if metrics.gates_passed else "FAIL — " + "; ".join(metrics.gate_failures))
        + "**",
        "",
        "## Per-case results",
        "",
        "| Case | Expected | Observed | Citations (obs/req) | Grounded | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        grounded = (
            "no cites" if not c.observed_citations else ("FAIL" if c.grounding_failures else "ok")
        )
        note = c.error or ("; ".join(c.grounding_failures) if c.grounding_failures else "")
        if c.intake_missing:
            note = f"intake bounced: {', '.join(c.intake_missing)}"
        observed = c.observed_outcome.value if c.observed_outcome else "ERROR"
        match = "✅" if c.observed_outcome == c.expected_outcome else "❌"
        obs_cites = ", ".join(c.observed_citations) or "—"
        req_cites = ", ".join(c.required_citations) or "—"
        lines.append(
            f"| {c.case_id} | {c.expected_outcome.value} | {observed} {match} "
            f"| {obs_cites} / {req_cites} | {grounded} | {note[:80]} |"
        )

    misses = [c for c in cases if c.observed_outcome != c.expected_outcome or c.error]
    lines += ["", "## Where it still fails", ""]
    if not misses:
        lines.append("No misses in this run. (Stay suspicious: n is small.)")
    for c in misses:
        observed = c.error or (c.observed_outcome.value if c.observed_outcome else "?")
        lines.append(f"- **{c.case_id}**: expected `{c.expected_outcome.value}`, got `{observed}`.")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report: wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
