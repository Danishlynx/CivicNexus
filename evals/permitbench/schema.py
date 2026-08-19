"""Eval case schema (ARCHITECTURE §9.1) and loader.

Every case is one YAML file under ``cases/``. ``docs`` are repo-relative paths
to the application documents the fleet receives (text in Phase 2; PDFs join in
Phase 5 with the adversarial set — recorded delta, see eval-report). Expected
citations name corpus section files, so an expectation can never reference law
that is not in the corpus — the loader enforces it.
"""

from pathlib import Path

import yaml
from civicnexus.contracts import DeterminationOutcome
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = Path(__file__).resolve().parent / "cases"
CORPUS_DIR = REPO_ROOT / "data" / "corpus"


class Expected(BaseModel):
    """Ground truth for one case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: DeterminationOutcome
    required_citations: list[str] = Field(default_factory=list)
    must_request: list[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    """One PermitBench case, verbatim field list from §9.1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    permit_type: str
    docs: list[str] = Field(min_length=1)
    applicant_profile: dict[str, str]
    expected: Expected
    tags: list[str] = Field(default_factory=list)


def load_case(path: Path) -> EvalCase:
    """Load and validate one case file, checking doc and citation references."""
    case = EvalCase.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    for doc in case.docs:
        if not (REPO_ROOT / doc).exists():
            raise FileNotFoundError(f"{path.name}: doc {doc} does not exist")
    for section in case.expected.required_citations:
        if not (CORPUS_DIR / f"{section}.txt").exists():
            raise FileNotFoundError(
                f"{path.name}: required citation {section} is not a corpus section"
            )
    return case


def load_all(tag: str | None = None) -> list[EvalCase]:
    """Load every case (optionally filtered by tag), sorted by id."""
    cases = [load_case(p) for p in sorted(CASES_DIR.glob("*.yaml"))]
    if tag is not None:
        cases = [c for c in cases if tag in c.tags]
    return cases
