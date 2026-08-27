"""Ablation reporting across archived arms (ADR-006 D9; ARCHITECTURE §9.5).

§9.5 wants two ablations charted — verifier off vs on (hallucinations caught)
and Model Armor off vs on (adversarial drill subset, isolated run). Both arms
of both ablations are produced by *other* programs and archived to
``evals/archive/``. This module measures nothing. It reads what those programs
wrote, pairs arms that are genuinely comparable, and refuses to pair arms that
are not — which is the whole reason it exists as a separate step rather than a
paragraph in a report template.

Three properties are load-bearing, and each one is a thing that has already
gone wrong somewhere in this industry:

  **Shape discrimination, not assumption.** ``evals/archive/`` holds two
  unrelated payload shapes: measured bench runs (``results-*.json`` from
  ``evals/runner.py``, carrying ``config.no_verifier``, no ``kind``) and drill
  runs (``{label}-{stamp}.json`` from ``drill_runner.archive()``, carrying
  ``kind: "drill_run"``). The shape is detected from the payload, and anything
  unreadable or unrecognised is skipped with a printed note rather than
  crashing a report or — far worse — being coerced into the nearest shape.

  **Unlabelled runs are never assigned an arm.** Archives written before D9's
  labelling rule carry no ``config`` at all. Guessing that such a run was the
  verifier-ON baseline would be exactly the "unlabelled files assembled later"
  failure D9 was written to prevent, so they are inventoried, named as
  unlabelled, and excluded from every pairing.

  **The armor-OFF arm is scoped, and the scope travels with the number.** Only
  text carriers can ride that arm: no PDF ingestion path exists (D9/A-12), so
  PDF fixtures are screening-layer only and have no unscreened counterpart. The
  emitted table therefore states, in its own output, how many gate fixtures the
  OFF arm excluded and why — a reader must not be able to mistake that arm for
  full coverage of the gate denominator.

The injection number is never quoted bare (B-014's binding reporting rule): it
ships with its sensitivity setting and the measured progression across
settings, with a clean negative arm at every step. The progression recorded in
BLOCKERS.md B-014 is reproduced with its provenance stated; an archive-derived
progression is emitted separately, and only when the archive actually holds
more than one sensitivity setting. The two are never merged, because one was
measured by this repo's canary runs and the other is a transcription.

The gate denominator is imported from the drills schema, never written down
here: it is structural (``len(InjectionFamily) * SEEDS_PER_FAMILY``), and
measured is 14 with one characterised holdout, so no literal count is a
threshold in this file.

Reads archived JSON and nothing else: no network, no client, no billed call.

Usage:
    uv run python -m evals.compare [--archive evals/archive] [--charts]
    uv run python -m evals.compare --require-both   # CI: missing arm is fatal
"""

import argparse
import importlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.permitbench.drills import schema as drills

REPO_ROOT = drills.REPO_ROOT
RUN_LOG = REPO_ROOT / ".deploy" / "compare_last_run.json"
ARCHIVE_DIR = REPO_ROOT / "evals" / "archive"
REPORT_PATH = REPO_ROOT / "docs" / "ablations.md"
CHART_DIR = REPO_ROOT / "docs"

#: Payload shapes this module knows how to read. Anything else is skipped by
#: name rather than coerced into whichever shape it superficially resembles.
SHAPE_MEASURED = "measured"
SHAPE_DRILL = "drill_run"

#: Arm names. ``unlabelled`` is a real, reportable state — it means the artifact
#: predates D9's config labelling and cannot be assigned to an arm at all.
ARM_VERIFIER_ON = "verifier_on"
ARM_VERIFIER_OFF = "verifier_off"
ARM_ARMOR_ON = "armor_on"
ARM_ARMOR_OFF = "armor_off"
ARM_UNLABELLED = "unlabelled"

#: Sensitivity settings the pi_and_jailbreak filter can carry (D5). Used to
#: recover a setting from an archive label when the config did not record one;
#: an unrecoverable setting is reported as unrecorded, never inferred.
_SENSITIVITY_TOKENS = ("low_and_above", "medium_and_above", "high")

#: The measured progression from BLOCKERS.md B-014, transcribed WITH its
#: provenance because B-014's reporting rule binds every place the injection
#: number appears: setting, progression, dilution finding, image-OCR gap.
#: Not recomputed here and never merged with archive-derived rows.
DOCUMENTED_PROGRESSION: tuple[tuple[str, str, str, str], ...] = (
    ("HIGH", "original", "0/15", "12 controls, 0 false positives"),
    ("MEDIUM_AND_ABOVE", "original", "2/15", "12 controls, 0 false positives"),
    ("MEDIUM_AND_ABOVE", "strengthened", "8/15", "12 controls, 0 false positives"),
    ("LOW_AND_ABOVE (shipped)", "strengthened", "14/15", "12 controls, 0 false positives"),
)
DOCUMENTED_PROGRESSION_SOURCE = (
    "BLOCKERS.md B-014, measured 2026-08-27 over three consecutive runs; transcribed here "
    "with provenance, NOT recomputed by this script"
)

#: Colourblind-safe pair, used the same way in every chart: blue = the arm with
#: the control in place, orange = the ablated arm.
_COLOR_CONTROL = "#1f6feb"
_COLOR_ABLATED = "#d1751a"

_record: dict[str, Any] = {"artifacts": [], "skipped": [], "steps": []}


def _log(name: str, **fields: Any) -> None:
    """Record a step in the evidence file and echo it, ASCII-safe for Windows."""
    _record["steps"].append({"step": name, "at": datetime.now(UTC).isoformat(), **fields})
    printable = {k: str(v)[:140] for k, v in fields.items()}
    print(f"compare: {name} {printable if fields else ''}")


def _persist() -> None:
    """Write evidence BEFORE any parsing or assertion can raise."""
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text(json.dumps(_record, indent=2, default=str), encoding="utf-8", newline="\n")


@dataclass(frozen=True)
class Artifact:
    """One archived arm, with the arm it declares about itself.

    ``arm`` is only ever what the payload says it is. Nothing in this module
    derives an arm from a filename, a timestamp, or a metric value.
    """

    path: Path
    shape: str
    arm: str
    label: str
    run_at: str
    project: str | None
    payload: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def name(self) -> str:
        """Short identity for tables: the label if there is one, else the file."""
        return self.label or self.path.name


class UnrecognisedArtifact(ValueError):
    """The file parsed as JSON but matches neither archived shape."""


def _engine_project(payload: dict[str, Any]) -> str | None:
    """Recover the project an arm was measured in, from whatever field carries it.

    Cross-project mixing is the quiet way a comparison table becomes wrong, so
    the project is extracted and checked rather than assumed uniform.
    """
    for candidate in (payload.get("engine"), payload.get("config", {}).get("engine")):
        if isinstance(candidate, str) and candidate.startswith("projects/"):
            parts = candidate.split("/")
            if len(parts) > 1:
                return parts[1]
    project = payload.get("project")
    return project if isinstance(project, str) else None


def classify(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(shape, arm, label)`` for one archived payload.

    Detection is by content: drill runs self-identify with ``kind``; measured
    runs are recognised by the metrics block ``evals/runner.py`` writes. A
    measured run without ``config.no_verifier`` predates D9 labelling and is
    returned as unlabelled — assigning it to the ON arm would be a guess that
    happens to be convenient, which is the exact failure mode D9 names.
    """
    if payload.get("kind") == SHAPE_DRILL:
        arm = str(payload.get("arm") or ARM_UNLABELLED)
        if arm not in (ARM_ARMOR_ON, ARM_ARMOR_OFF):
            arm = ARM_UNLABELLED
        return SHAPE_DRILL, arm, str(payload.get("label") or "")

    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and "decision_accuracy" in metrics:
        config = payload.get("config")
        if not isinstance(config, dict) or "no_verifier" not in config:
            return SHAPE_MEASURED, ARM_UNLABELLED, ""
        arm = ARM_VERIFIER_OFF if bool(config["no_verifier"]) else ARM_VERIFIER_ON
        return SHAPE_MEASURED, arm, str(payload.get("label") or "")

    raise UnrecognisedArtifact("no 'kind: drill_run' and no metrics.decision_accuracy block")


def read_artifact(path: Path) -> Artifact:
    """Parse one archive file into an :class:`Artifact`, or raise a named cause.

    Raises rather than returning a placeholder so the caller decides how a bad
    file is reported; a silently dropped file is a silently shrunk comparison.
    """
    raw = path.read_text(encoding="utf-8-sig")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise UnrecognisedArtifact(f"top level is {type(payload).__name__}, expected an object")
    shape, arm, label = classify(payload)
    return Artifact(
        path=path,
        shape=shape,
        arm=arm,
        label=label,
        run_at=str(payload.get("run_at") or ""),
        project=_engine_project(payload),
        payload=payload,
    )


def discover(archive_dir: Path, *, project: str) -> tuple[list[Artifact], list[tuple[Path, str]]]:
    """Read every JSON in the archive, returning what was usable and what was not.

    Unreadable, unparseable and cross-project files are returned as skips with a
    cause instead of raising: one corrupt file must not deny the report of the
    arms that ARE intact, and a stale artifact from another project must never
    be silently averaged into this project's numbers.
    """
    artifacts: list[Artifact] = []
    skipped: list[tuple[Path, str]] = []
    for path in sorted(archive_dir.glob("*.json")):
        try:
            artifact = read_artifact(path)
        except Exception as exc:  # never crash the report on one bad file
            skipped.append((path, f"{type(exc).__name__}: {exc}"))
            _record["skipped"].append({"file": path.name, "cause": f"{type(exc).__name__}: {exc}"})
            _persist()
            print(f"compare: SKIPPED {path.name} - {type(exc).__name__}: {exc}")
            continue
        if project and artifact.project is not None and artifact.project != project:
            cause = f"measured in project {artifact.project}, not PROJECT_ID {project}"
            skipped.append((path, cause))
            _record["skipped"].append({"file": path.name, "cause": cause})
            _persist()
            print(f"compare: SKIPPED {path.name} - {cause}")
            continue
        artifacts.append(artifact)
        _record["artifacts"].append(
            {
                "file": path.name,
                "shape": artifact.shape,
                "arm": artifact.arm,
                "label": artifact.label,
                "run_at": artifact.run_at,
                "project": artifact.project,
            }
        )
        _persist()
    return artifacts, skipped


def latest(artifacts: list[Artifact], shape: str, arm: str) -> Artifact | None:
    """Most recent artifact for one arm, or None when that arm was never archived."""
    candidates = [a for a in artifacts if a.shape == shape and a.arm == arm]
    if not candidates:
        return None
    return sorted(candidates, key=lambda a: (a.run_at, a.path.name))[-1]


# ------------------------------------------------- ablation 1: verifier off/on
def verifier_row(artifact: Artifact) -> dict[str, Any]:
    """Per-arm numbers for the "hallucinations caught" comparison (§9.5).

    ``--no-verifier`` still verifies once in observe-only mode (D9's pinned
    semantics), so both arms carry first-pass data and the arms differ in
    exactly one thing: whether a failed verification was allowed to trigger the
    §7.3 corrective retry. ``caught`` counts first-pass failures — findings the
    verifier judged unsupported — and ``corrected`` counts the subset the retry
    actually repaired, which is a number only the ON arm can be nonzero on.
    """
    payload = artifact.payload
    metrics = payload.get("metrics", {})
    cases = payload.get("cases", [])
    cases = cases if isinstance(cases, list) else []

    scored = [c for c in cases if c.get("verifier_first_pass") is not None]
    caught = [c for c in scored if not c["verifier_first_pass"]]
    retried = [c for c in cases if c.get("verifier_retried")]
    corrected = [c for c in retried if c.get("verifier_final_passed")]
    unresolved = [c for c in cases if c.get("verifier_final_passed") is False]
    return {
        "artifact": artifact.name,
        "file": artifact.path.name,
        "run_at": artifact.run_at,
        "tag": payload.get("tag"),
        "cases": metrics.get("cases"),
        "errors": metrics.get("errors"),
        "decision_accuracy": metrics.get("decision_accuracy"),
        "citation_precision": metrics.get("citation_precision"),
        "citation_recall": metrics.get("citation_recall"),
        "groundedness_first_pass": metrics.get("groundedness_first_pass"),
        "verifier_first_pass": metrics.get("verifier_first_pass"),
        "leak_rate": metrics.get("leak_rate"),
        "tokens_total": metrics.get("tokens_total"),
        "verifier_scored": len(scored),
        "caught_first_pass_failures": len(caught),
        "retried": len(retried),
        "corrected_by_retry": len(corrected),
        "unresolved_after_retry": len(unresolved),
        "grounding_failure_cases": sum(1 for c in cases if c.get("grounding_failures")),
    }


# ---------------------------------------------------- ablation 2: armor off/on
def armor_scope() -> dict[str, Any]:
    """How much of the gate corpus the armor-OFF arm can cover, and what it cannot.

    Computed from the shipped corpus rather than quoted, so the exclusion count
    in the table tracks the fixtures that actually exist. Failure to load the
    corpus is returned as a cause: a scope line that silently reports zero
    exclusions would be the single most misleading output this module could
    produce.
    """
    scope: dict[str, Any] = {
        "denominator": drills.GATE_DENOMINATOR,
        "eligible": None,
        "excluded": None,
        "reason": (
            "PDF carriers are screening-layer only: no PDF ingestion path exists, so those "
            "fixtures have no unscreened counterpart and their screening result never "
            "transfers to the armor-OFF arm (ADR-006 D9 / A-12)"
        ),
    }
    try:
        fixtures = drills.gate_fixtures()
    except Exception as exc:  # named, never swallowed
        scope["error"] = f"{type(exc).__name__}: {exc}"
        return scope
    scope["loaded"] = len(fixtures)
    scope["eligible"] = sum(1 for f in fixtures if not f.screening_layer_only)
    scope["excluded"] = sum(1 for f in fixtures if f.screening_layer_only)
    scope["excluded_ids"] = [f.id for f in fixtures if f.screening_layer_only]
    return scope


def armor_on_row(artifact: Artifact) -> dict[str, Any]:
    """Gate and negative-control numbers from an archived armor-ON drill run."""
    payload = artifact.payload
    gate = payload.get("gate", {})
    controls = payload.get("negative_controls", {})
    config = payload.get("config", {})
    return {
        "artifact": artifact.name,
        "file": artifact.path.name,
        "run_at": artifact.run_at,
        "sensitivity": sensitivity_of(artifact),
        "denominator": gate.get("denominator", drills.GATE_DENOMINATOR),
        "loaded": gate.get("loaded"),
        "attributed": gate.get("attributed"),
        "expected": gate.get("expected"),
        "expected_filter_exact": gate.get("expected_filter_exact"),
        "misses": gate.get("misses", []),
        "controls": controls.get("controls"),
        "false_positives": controls.get("false_positives", []),
        "counted_filters": config.get("counted_filters", []),
        "coverage": "all carriers (screening layer)",
    }


def armor_off_row(artifact: Artifact) -> dict[str, Any]:
    """Signal counts from an archived armor-OFF drill run, carrying its exclusion.

    The exclusion recorded by ``drill_runner`` at run time is preferred over
    anything recomputed here: the arm's own record of what it skipped is the
    only description guaranteed to match what it actually ran.
    """
    payload = artifact.payload
    plan = payload.get("plan", {})
    config = payload.get("config", {})
    return {
        "artifact": artifact.name,
        "file": artifact.path.name,
        "run_at": artifact.run_at,
        "ran": bool(plan.get("ran")),
        "planned_cases": plan.get("planned_cases"),
        "completed_cases": plan.get("completed_cases"),
        "partial": plan.get("partial"),
        "aborted_on_tokens": plan.get("aborted_on_tokens"),
        "tokens_total": plan.get("tokens_total"),
        "signal_counts": plan.get("signal_counts", {}),
        "errors": plan.get("errors", []),
        "excluded_cases": config.get("excluded_cases", plan.get("excluded_cases")),
        "excluded_reason": config.get("excluded_reason", plan.get("excluded_reason")),
        "coverage": "text carriers only",
    }


# --------------------------------------------------- injection-gate progression
def sensitivity_of(artifact: Artifact) -> str:
    """The pi_and_jailbreak sensitivity an arm ran at, or ``unrecorded``.

    Read from config where the arm recorded it, else recovered from the archive
    label, which is where the canary re-runs of B-014 carried it. Never guessed
    from the score: inferring the setting from the number it produced would
    make the progression table circular.
    """
    config = artifact.payload.get("config", {})
    config = config if isinstance(config, dict) else {}
    for key in ("confidence_level", "sensitivity", "pi_and_jailbreak_confidence"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    haystack = f"{artifact.label} {artifact.path.stem}".lower()
    for token in _SENSITIVITY_TOKENS:
        if re.search(rf"\b{token}\b|[-_]{token}", haystack):
            return token.upper()
    return "unrecorded"


def archive_progression(artifacts: list[Artifact]) -> list[dict[str, Any]]:
    """Archive-derived gate progression, one row per armor-ON run, oldest first.

    Emitted only when the archive genuinely holds more than one sensitivity
    setting; a single-setting archive has no progression to show and gets the
    documented B-014 table alone, clearly marked as a transcription.
    """
    rows = [armor_on_row(a) for a in artifacts if a.shape == SHAPE_DRILL and a.arm == ARM_ARMOR_ON]
    return sorted(rows, key=lambda r: str(r["run_at"]))


# ----------------------------------------------------------------- rendering
def _pct(value: Any) -> str:
    """Percent for a rate, or a dash when the arm never recorded one."""
    if isinstance(value, int | float):
        return f"{float(value) * 100:.1f}%"
    return "-"


def _num(value: Any) -> str:
    """Integer for a count, or a dash when the arm never recorded one."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int | float):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return "-"


def _delta(on: Any, off: Any, *, as_pct: bool) -> str:
    """Signed ON-minus-OFF delta, or a dash when either arm is missing the value."""
    if not isinstance(on, int | float) or not isinstance(off, int | float):
        return "-"
    diff = float(on) - float(off)
    return f"{diff * 100:+.1f} pp" if as_pct else f"{diff:+,.0f}"


def _inventory_lines(artifacts: list[Artifact], skipped: list[tuple[Path, str]]) -> list[str]:
    """Everything the archive offered and what became of it, including the skips."""
    lines = [
        "## What the archive held",
        "",
        "| File | Shape | Arm | Run at | Used for |",
        "|---|---|---|---|---|",
    ]
    for artifact in artifacts:
        if artifact.arm == ARM_UNLABELLED:
            use = "NOT PAIRED - no arm label (predates ADR-006 D9 config labelling)"
        elif artifact.shape == SHAPE_MEASURED:
            use = "verifier ablation"
        else:
            use = "Model Armor ablation"
        lines.append(
            f"| `{artifact.path.name}` | {artifact.shape} | {artifact.arm} | "
            f"{artifact.run_at or '-'} | {use} |"
        )
    for path, cause in skipped:
        lines.append(f"| `{path.name}` | SKIPPED | - | - | {cause} |")
    if not artifacts and not skipped:
        lines.append("| (empty) | - | - | - | no JSON artifacts in the archive |")
    lines.append("")
    lines.append(
        "An artifact with no `config.no_verifier` cannot be assigned to an arm without "
        "guessing, so it is listed and excluded rather than folded into the baseline. "
        "The shipping `evals/results.json` is not read here for the same reason: it is a "
        "headline, not a labelled arm."
    )
    lines.append("")
    return lines


#: Rows of the verifier ablation table: ``(label, key, render_as_percent,
#: off_arm_note)``. Declared once so both arms are formatted by identical code —
#: a table where the ON column and the OFF column are built by two hand-written
#: expressions is a table where one of them can quietly use a different metric.
_VERIFIER_METRICS: tuple[tuple[str, str, bool, str], ...] = (
    ("Cases scored", "cases", False, ""),
    ("Errors", "errors", False, ""),
    ("Decision accuracy", "decision_accuracy", True, ""),
    ("Groundedness first-pass", "groundedness_first_pass", True, ""),
    ("Citation precision", "citation_precision", True, ""),
    ("Citation recall", "citation_recall", True, ""),
    ("Verifier first-pass rate", "verifier_first_pass", True, ""),
    ("Caught (first-pass failures)", "caught_first_pass_failures", False, ""),
    ("Corrected by retry", "corrected_by_retry", False, " (retry disabled)"),
    ("Unresolved after verification", "unresolved_after_retry", False, ""),
    ("Cases with grounding failures", "grounding_failure_cases", False, ""),
    ("Canary leak rate", "leak_rate", True, ""),
    ("Tokens (run total)", "tokens_total", False, ""),
)


def _verifier_lines(on: Artifact | None, off: Artifact | None) -> list[str]:
    """The verifier ablation section, stating plainly when it is not a comparison."""
    lines = ["## Ablation 1 - verifier OFF vs ON (hallucinations caught)", ""]
    lines.append(
        "`evals/runner.py --no-verifier` keeps verification running once in observe-only "
        "mode (ADR-006 D9 pinned semantics), so both arms carry first-pass data. The arms "
        "differ in exactly one thing: whether a failed verification was allowed to trigger "
        "the 7.3 corrective retry. `caught` is what the verifier flagged; `corrected` is "
        "what the retry repaired, and only the ON arm can be nonzero there."
    )
    lines.append("")
    if on is None or off is None:
        present = "ON only" if on is not None else ("OFF only" if off is not None else "neither")
        lines.append(
            f"**No comparison available.** Arms archived: {present}. A verifier ablation "
            "needs one labelled `config.no_verifier: false` run and one labelled "
            "`config.no_verifier: true` run in `evals/archive/`. No delta is shown, and "
            "no arm is estimated from the other."
        )
        lines.append("")
        present_arm = on if on is not None else off
        if present_arm is not None:
            single = verifier_row(present_arm)
            lines.extend(
                [
                    f"Present arm only (`{single['file']}`, run at {single['run_at']}): "
                    f"{_num(single['cases'])} cases, accuracy "
                    f"{_pct(single['decision_accuracy'])}, verifier first-pass "
                    f"{_pct(single['verifier_first_pass'])}, caught "
                    f"{_num(single['caught_first_pass_failures'])} of "
                    f"{_num(single['verifier_scored'])} scored. This is one arm's number, "
                    "not an ablation result.",
                    "",
                ]
            )
        return lines

    row_on, row_off = verifier_row(on), verifier_row(off)
    lines.extend(
        [
            f"ON arm: `{row_on['file']}` ({row_on['run_at']}, tag `{row_on['tag'] or 'all'}`) - "
            f"OFF arm: `{row_off['file']}` ({row_off['run_at']}, tag "
            f"`{row_off['tag'] or 'all'}`).",
            "",
            "| Metric | Verifier ON | Verifier OFF | Delta (ON - OFF) |",
            "|---|---|---|---|",
        ]
    )
    for label, key, as_pct, off_note in _VERIFIER_METRICS:
        fmt = _pct if as_pct else _num
        lines.append(
            f"| {label} | {fmt(row_on[key])} | {fmt(row_off[key])}{off_note} | "
            f"{_delta(row_on[key], row_off[key], as_pct=as_pct)} |"
        )
    lines.append("")
    if row_on["tag"] != row_off["tag"] or row_on["cases"] != row_off["cases"]:
        lines.append(
            "**Caution: the arms are not case-matched.** They ran different tags or "
            "different case counts, so the delta mixes the ablation with a corpus "
            "difference. Re-run both arms on the same tag before quoting these numbers."
        )
        lines.append("")
    return lines


def _armor_lines(on: Artifact | None, off: Artifact | None, scope: dict[str, Any]) -> list[str]:
    """The armor ablation section. The scoping statement leads, by design."""
    lines = ["## Ablation 2 - Model Armor OFF vs ON (adversarial drill subset)", ""]

    if "error" in scope:
        coverage = (
            f"**Scope of the OFF arm could not be computed** - the drill corpus failed to "
            f"load ({scope['error']}). Treat any OFF-arm number below as unscoped until "
            f"this is fixed."
        )
    else:
        coverage = (
            f"**Scope: the OFF arm is NOT full coverage of the gate corpus.** Of "
            f"{scope['denominator']} injection gate fixtures, only {scope['eligible']} can "
            f"ride the armor-OFF arm; **{scope['excluded']} are excluded**. "
            f"{scope['reason']}. An armor-OFF result therefore speaks for text carriers "
            f"only and must never be quoted against the full gate denominator."
        )
    lines.extend([coverage, ""])
    if scope.get("excluded_ids"):
        lines.append("Excluded fixtures: " + ", ".join(f"`{i}`" for i in scope["excluded_ids"]))
        lines.append("")

    if on is None and off is None:
        lines.append(
            "**No arms archived.** Run `python -m evals.drill_runner` (ON) and "
            "`python -m evals.drill_runner --armor off --i-have-a-spend-ok` (OFF, BILLED) "
            "to populate this section. Nothing is estimated in their absence."
        )
        lines.append("")
        return lines

    row_on = armor_on_row(on) if on is not None else None
    row_off = armor_off_row(off) if off is not None else None

    lines.extend(
        [
            "| Aspect | Model Armor ON | Model Armor OFF |",
            "|---|---|---|",
        ]
    )
    if row_on is None:
        on_cells = ["not archived"] * 5
    else:
        on_cells = [
            f"`{row_on['file']}` ({row_on['run_at']})",
            f"{row_on['coverage']} - {_num(row_on['loaded'])} of "
            f"{_num(row_on['denominator'])} fixtures",
            f"{_num(row_on['attributed'])}/{_num(row_on['denominator'])} attributed to a "
            f"blocking filter (exact-filter {_num(row_on['expected_filter_exact'])})",
            ", ".join(row_on["misses"]) if row_on["misses"] else "none",
            f"{_num(row_on['controls'])} controls, "
            f"{len(row_on['false_positives'])} false positives",
        ]
    if row_off is None:
        off_cells = ["not archived"] * 5
    elif not row_off["ran"]:
        off_cells = [
            f"`{row_off['file']}` ({row_off['run_at']})",
            f"{row_off['coverage']} - {_num(row_off['planned_cases'])} planned",
            "PLAN ONLY - no engine call was issued, nothing measured",
            "n/a",
            "n/a",
        ]
    else:
        signals = row_off["signal_counts"] or {}
        off_cells = [
            f"`{row_off['file']}` ({row_off['run_at']})",
            f"{row_off['coverage']} - {_num(row_off['completed_cases'])} of "
            f"{_num(row_off['planned_cases'])} run" + (" (PARTIAL)" if row_off["partial"] else ""),
            "no screening layer; unscreened pipeline signals: "
            + (", ".join(f"{k} {v}" for k, v in signals.items()) if signals else "none recorded"),
            f"errors: {', '.join(row_off['errors']) if row_off['errors'] else 'none'}",
            f"tokens {_num(row_off['tokens_total'])}"
            + (" - ABORTED on the token ceiling" if row_off["aborted_on_tokens"] else ""),
        ]
    for label, on_cell, off_cell in zip(
        (
            "Arm artifact",
            "Coverage",
            "Result",
            "Misses / errors",
            "Negative controls / cost",
        ),
        on_cells,
        off_cells,
        strict=True,
    ):
        lines.append(f"| {label} | {on_cell} | {off_cell} |")
    lines.append("")
    lines.append(
        "The two arms measure different things and are placed side by side, never "
        "subtracted: ON counts screening-layer blocks over the whole corpus, OFF counts "
        "behavioural signals over the text-carrier subset that has an unscreened path. "
        "A signal on the OFF arm is an indicator, not proof of obedience."
    )
    lines.append("")
    if row_off is not None and row_off["excluded_reason"]:
        lines.append(
            f"The OFF arm recorded its own exclusion at run time: "
            f"{_num(row_off['excluded_cases'])} fixtures - {row_off['excluded_reason']}"
        )
        lines.append("")
    return lines


def _progression_lines(rows: list[dict[str, Any]]) -> list[str]:
    """The injection-gate progression, with archive and transcription kept apart."""
    lines = ["## Injection gate: sensitivity progression", ""]
    lines.append(
        "B-014's reporting rule binds here: the injection number is never quoted bare. It "
        "ships with the sensitivity setting, this progression, the dilution finding, and "
        "the image-OCR coverage gap."
    )
    lines.append("")

    settings = {str(r["sensitivity"]) for r in rows}
    if len(rows) > 1 and len(settings - {"unrecorded"}) > 1:
        lines.extend(
            [
                "### Measured in this archive",
                "",
                "| Run at | Setting | Gate | Exact-filter | Misses | False positives |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['run_at'] or '-'} | {row['sensitivity']} | "
                f"{_num(row['attributed'])}/{_num(row['denominator'])} | "
                f"{_num(row['expected_filter_exact'])} | "
                f"{', '.join(row['misses']) if row['misses'] else 'none'} | "
                f"{len(row['false_positives'])} |"
            )
        lines.append("")
    elif rows:
        lines.append(
            f"The archive holds {len(rows)} armor-ON run(s) at "
            f"{len(settings)} recorded setting(s) "
            f"({', '.join(sorted(settings))}), which is not a progression. The measured "
            "progression below is reproduced from the record that established it."
        )
        lines.append("")
    else:
        lines.append(
            "No armor-ON drill run is archived, so no progression is derived here. The "
            "table below is the record that established the shipped setting."
        )
        lines.append("")

    lines.extend(
        [
            "### Measured progression of record",
            "",
            f"Source: {DOCUMENTED_PROGRESSION_SOURCE}.",
            "",
            "| Setting | Fixtures | Positive arm | Negative arm |",
            "|---|---|---|---|",
        ]
    )
    for setting, fixtures, positive, negative in DOCUMENTED_PROGRESSION:
        lines.append(f"| {setting} | {fixtures} | {positive} | {negative} |")
    lines.extend(
        [
            "",
            "Every loosening was kept only because the negative arm stayed clean, so the "
            "added sensitivity is measured to have cost nothing rather than assumed to be "
            "free. `confidence_level` is the MINIMUM confidence at which the filter "
            "reports, so HIGH is the LEAST sensitive setting despite reading like the "
            "strongest.",
            "",
            "The single holdout is characterised and deliberately not tuned away: "
            "`adv-001-white-text-approve-override-hobby-shed` sits at a 46% injection "
            "share between two siblings at 45% and 47% that both pass, and its "
            "instruction matches when screened standalone. That is boundary behaviour at "
            "a dilution ratio, not a defect, and editing the fixture until it passed "
            "would be fitting the test to the system.",
            "",
            "Coverage gap, stated with the number: screening does not read text out of "
            "embedded raster images, so image-OCR injection is undetectable by "
            "construction here and no fixture claims it (ADR-006 A-12).",
            "",
        ]
    )
    return lines


def render(
    *,
    artifacts: list[Artifact],
    skipped: list[tuple[Path, str]],
    project: str,
    archive_dir: Path,
    charts: list[str],
    chart_note: str,
) -> str:
    """Build the whole markdown report, arms and non-arms alike.

    One renderer feeds both stdout and `docs/ablations.md`, so the file a judge
    reads and the text the operator saw can never disagree.
    """
    verifier_on = latest(artifacts, SHAPE_MEASURED, ARM_VERIFIER_ON)
    verifier_off = latest(artifacts, SHAPE_MEASURED, ARM_VERIFIER_OFF)
    armor_on = latest(artifacts, SHAPE_DRILL, ARM_ARMOR_ON)
    armor_off = latest(artifacts, SHAPE_DRILL, ARM_ARMOR_OFF)

    lines = [
        "# Ablations (ARCHITECTURE 9.5, ADR-006 D9)",
        "",
        f"Generated by `evals/compare.py` at {datetime.now(UTC).isoformat()} from "
        f"`{archive_dir.as_posix()}`, project `{project}`. Reads archived JSON only - no "
        "network call, no billed operation, nothing re-measured. Do not hand-edit.",
        "",
    ]
    lines.extend(_inventory_lines(artifacts, skipped))
    lines.extend(_verifier_lines(verifier_on, verifier_off))
    lines.extend(_armor_lines(armor_on, armor_off, armor_scope()))
    lines.extend(_progression_lines(archive_progression(artifacts)))

    lines.extend(["## Charts", ""])
    if charts:
        lines.extend([f"- `{c}`" for c in charts])
    else:
        lines.append(f"No charts written: {chart_note}")
    lines.append("")
    lines.extend(
        [
            "## What this report does not claim",
            "",
            "- Nothing here was measured by this script; every number is read from an arm "
            "another program archived, and the file it came from is named beside it.",
            "- Arms are paired only when both carry an explicit label. An unlabelled or "
            "single-arm section says so instead of showing a delta.",
            "- The armor-OFF arm covers text carriers only; its numbers do not describe "
            "the PDF fixtures and are not a statement about the full gate denominator.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- charts
def write_charts(artifacts: list[Artifact]) -> tuple[list[str], str]:
    """Write the §9.5 PNGs if the data for them exists, else say why it does not.

    matplotlib is not a project dependency, so its absence is a clean skip with
    a note rather than an error. No chart is ever drawn from a single arm or
    padded to look complete: a half-populated ablation chart reads as a finding.
    """
    try:
        # Imported through importlib because matplotlib is NOT a project
        # dependency: a plain import would make every static check in CI depend
        # on an optional package that the tables above do not need.
        matplotlib = importlib.import_module("matplotlib")
        matplotlib.use("Agg")  # headless; no display is ever available here
        plt = importlib.import_module("matplotlib.pyplot")
    except Exception as exc:
        return [], (
            f"matplotlib unavailable ({type(exc).__name__}: {exc}); it is not a project "
            "dependency. Install it in the dev group to render the PNGs; the tables above "
            "are unaffected."
        )

    written: list[str] = []
    notes: list[str] = []
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    verifier_on = latest(artifacts, SHAPE_MEASURED, ARM_VERIFIER_ON)
    verifier_off = latest(artifacts, SHAPE_MEASURED, ARM_VERIFIER_OFF)
    row_on = verifier_row(verifier_on) if verifier_on is not None else None
    row_off = verifier_row(verifier_off) if verifier_off is not None else None
    if row_on is not None and row_off is not None:
        # Only metrics BOTH arms actually recorded are plotted. A missing value
        # rendered as a zero-height bar is a fabricated data point that reads as
        # a catastrophic score, so the bar is omitted and the omission is noted.
        candidates = [
            ("Decision\naccuracy", "decision_accuracy"),
            ("Groundedness\nfirst-pass", "groundedness_first_pass"),
            ("Verifier\nfirst-pass", "verifier_first_pass"),
        ]
        plotted = [
            (text, key)
            for text, key in candidates
            if isinstance(row_on[key], int | float) and isinstance(row_off[key], int | float)
        ]
        dropped = [key for _, key in candidates if (key not in {k for _, k in plotted})]
        if dropped:
            notes.append(
                "verifier chart omits " + ", ".join(dropped) + ": one or both arms never "
                "recorded that metric, and a zero bar would invent one"
            )
    else:
        plotted = []
        notes.append("verifier chart skipped: both labelled arms are required and are not present")

    if row_on is not None and row_off is not None and plotted:
        labels = [text for text, _ in plotted]
        keys = [key for _, key in plotted]
        on_values = [float(row_on[k]) * 100 for k in keys]
        off_values = [float(row_off[k]) * 100 for k in keys]
        figure, axes = plt.subplots(figsize=(7.0, 4.0))
        positions = range(len(labels))
        axes.bar(
            [p - 0.19 for p in positions],
            on_values,
            width=0.38,
            label="verifier ON",
            color=_COLOR_CONTROL,
        )
        axes.bar(
            [p + 0.19 for p in positions],
            off_values,
            width=0.38,
            label="verifier OFF (observe-only)",
            color=_COLOR_ABLATED,
        )
        axes.set_xticks(list(positions))
        axes.set_xticklabels(labels)
        axes.set_ylim(0, 100)
        axes.set_ylabel("percent")
        axes.set_title(
            f"Verifier ablation - {row_on['cases']} vs {row_off['cases']} cases "
            f"(tags {row_on['tag']} / {row_off['tag']})"
        )
        axes.legend(frameon=False)
        axes.spines["top"].set_visible(False)
        axes.spines["right"].set_visible(False)
        figure.tight_layout()
        path = CHART_DIR / "ablation-verifier.png"
        figure.savefig(path, dpi=144)
        plt.close(figure)
        written.append(path.relative_to(REPO_ROOT).as_posix())
    elif row_on is not None and row_off is not None:
        notes.append(
            "verifier chart skipped: both arms are present but share no metric they both "
            "recorded, so there is nothing to plot honestly"
        )

    # Same rule on the progression: a run whose gate count was never recorded is
    # dropped from the chart rather than drawn at zero.
    rows = [r for r in archive_progression(artifacts) if isinstance(r["attributed"], int | float)]
    settings = {str(r["sensitivity"]) for r in rows}
    if len(rows) > 1 and len(settings - {"unrecorded"}) > 1:
        figure, axes = plt.subplots(figsize=(7.0, 4.0))
        heights = [float(r["attributed"]) for r in rows]
        denominator = float(rows[0]["denominator"] or drills.GATE_DENOMINATOR)
        axes.bar(
            range(len(rows)),
            heights,
            width=0.55,
            color=_COLOR_CONTROL,
        )
        axes.set_xticks(list(range(len(rows))))
        axes.set_xticklabels([str(r["sensitivity"]) for r in rows], rotation=20, ha="right")
        axes.set_ylim(0, denominator)
        axes.set_ylabel(f"fixtures attributed (of {denominator:.0f})")
        axes.set_title("Injection gate by sensitivity setting - measured in this archive")
        axes.spines["top"].set_visible(False)
        axes.spines["right"].set_visible(False)
        figure.tight_layout()
        path = CHART_DIR / "injection-gate-progression.png"
        figure.savefig(path, dpi=144)
        plt.close(figure)
        written.append(path.relative_to(REPO_ROOT).as_posix())
    else:
        notes.append(
            "progression chart skipped: the archive holds fewer than two recorded "
            "sensitivity settings, and the B-014 table is a transcription, not data this "
            "script measured - charting it would imply otherwise"
        )

    # The armor ablation is deliberately NOT charted as paired bars: the arms
    # count different things over different corpora (screening blocks over all
    # carriers vs behavioural signals over text carriers), so a shared axis
    # would assert a comparability the arms do not have. The table carries it.
    notes.append(
        "armor ablation left as a table: its arms count different things over different "
        "corpora, so a shared axis would assert a comparability they do not have"
    )
    return written, "; ".join(notes)


# -------------------------------------------------------------------- driver
def main() -> int:
    """Render the ablation comparison and print a PASS/FAIL scoped to what existed."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", default=str(ARCHIVE_DIR), help="directory of archived arms to read"
    )
    parser.add_argument("--out", default=str(REPORT_PATH), help="markdown output path")
    parser.add_argument(
        "--charts", action="store_true", help="also write PNGs to docs/ when the data exists"
    )
    parser.add_argument(
        "--require-both",
        action="store_true",
        help="fail when either ablation is missing an arm (for a CI or pre-submission check)",
    )
    args = parser.parse_args()

    # PROJECT_ID is OPTIONAL here, deliberately. This tool only reads archived
    # JSON - no network, no billed call - so requiring cloud env to regenerate a
    # report would be a barrier with no safety value. When it IS set it earns
    # its keep by refusing artifacts measured in a different project, which is
    # how numbers from two projects end up in one table. When it is not, that
    # protection is announced as OFF rather than silently skipped.
    project = os.environ.get("PROJECT_ID", "").strip()
    if not project:
        print(
            "compare: NOTE - PROJECT_ID unset, so cross-project artifact "
            "filtering is OFF; every archived artifact is included"
        )

    archive_dir = Path(args.archive)
    out_path = Path(args.out)
    _record["project"] = project
    _record["archive_dir"] = str(archive_dir)
    _record["out"] = str(out_path)
    _record["started_at"] = datetime.now(UTC).isoformat()
    _persist()

    if not archive_dir.is_dir():
        _record["error"] = f"archive dir missing: {archive_dir}"
        _persist()
        print(f"FAIL: compare - archive directory not found: {archive_dir}")
        return 1

    artifacts, skipped = discover(archive_dir, project=project)
    _log("discovered", usable=len(artifacts), skipped=len(skipped))
    if not artifacts:
        _record["finished_at"] = datetime.now(UTC).isoformat()
        _persist()
        print(
            f"FAIL: compare - no readable arm in {archive_dir} "
            f"({len(skipped)} file(s) skipped); nothing to compare"
        )
        return 1

    charts: list[str] = []
    chart_note = "charts not requested (pass --charts)"
    if args.charts:
        try:
            charts, chart_note = write_charts(artifacts)
        except Exception as exc:  # a chart failure must not lose the tables
            chart_note = f"chart rendering failed: {type(exc).__name__}: {exc}"
            print(f"compare: chart rendering failed - {type(exc).__name__}: {exc}")
    _record["charts"] = charts
    _record["chart_note"] = chart_note
    _persist()

    markdown = render(
        artifacts=artifacts,
        skipped=skipped,
        project=project,
        archive_dir=archive_dir,
        charts=charts,
        chart_note=chart_note,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8", newline="\n")
    _record["report_bytes"] = len(markdown)
    _persist()

    print()
    print(markdown)

    verifier_arms = sum(
        1
        for arm in (ARM_VERIFIER_ON, ARM_VERIFIER_OFF)
        if latest(artifacts, SHAPE_MEASURED, arm) is not None
    )
    armor_arms = sum(
        1
        for arm in (ARM_ARMOR_ON, ARM_ARMOR_OFF)
        if latest(artifacts, SHAPE_DRILL, arm) is not None
    )
    unlabelled = sum(1 for a in artifacts if a.arm == ARM_UNLABELLED)
    _record["verifier_arms"] = verifier_arms
    _record["armor_arms"] = armor_arms
    _record["unlabelled"] = unlabelled
    _record["finished_at"] = datetime.now(UTC).isoformat()
    _persist()

    def _scope(name: str, count: int) -> str:
        if count == 2:
            return f"{name} BOTH ARMS"
        if count == 1:
            return f"{name} ONE ARM ONLY - not a comparison"
        return f"{name} NO ARMS"

    scope = (
        f"{len(artifacts)} artifacts read, {len(skipped)} skipped, "
        f"{unlabelled} unlabelled; {_scope('verifier', verifier_arms)}; "
        f"{_scope('armor', armor_arms)}"
    )
    print(f"compare: wrote {out_path}")
    if charts:
        print(f"compare: charts {', '.join(charts)}")
    else:
        print(f"compare: no charts - {chart_note}")

    if args.require_both and (verifier_arms < 2 or armor_arms < 2):
        print(f"FAIL: compare - --require-both given but arms are incomplete ({scope})")
        return 1
    print(f"PASS: compare ({scope}); evidence {RUN_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
