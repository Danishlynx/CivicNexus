"""Compose a fact sheet into a determination with citations the corpus backs.

Pure apart from reading the committed corpus: same fact sheet in, byte-identical
result out, every run. That is the whole point — the §7.3 verifier already
proved the deterministic string checks were the part of the pipeline carrying
its weight ("its value in this system is citation fidelity, not decision
correction", PROGRESS 2026-08-26 ablation), so the decision joins them.

Quotes are located in ``data/corpus/<section>.txt`` rather than emitted from
the rule table, so a corpus edit that orphans a rule's anchor fails loudly here
instead of producing a citation the verifier will silently reject.
"""

from pathlib import Path
from typing import Any

from civicnexus.contracts import Citation, DeterminationOutcome, ReviewFinding
from civicnexus.contracts.permit_types import PermitTypeConfig
from civicnexus.decision.facts import FactSheet, ProvisionFact
from civicnexus.decision.rules import SECTIONS, element_by_eid, rule_for_permit_type
from pydantic import BaseModel, ConfigDict, Field


class UndecidableError(RuntimeError):
    """The rule layer has no rules for the sections this fact sheet engages.

    Raised rather than guessed. A caller should record the case as undecided by
    the code layer — inventing a determination here would be exactly the
    fabrication the whole design exists to remove.
    """


class DecisionResult(BaseModel):
    """A determination reached by code, ready to become a ``ReviewFinding``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: DeterminationOutcome
    citations: list[Citation] = Field(min_length=1)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    controlling_provisions: list[str] = Field(default_factory=list)
    #: What a request_info asks the applicant for, in section order.
    missing_elements: list[str] = Field(default_factory=list)
    #: False when the outcome is not in the permit type's ``allowed_outcomes``.
    #: The outcome is NOT rewritten to fit: steering an outcome from config is
    #: prime-directive-9 territory, and the verifier's step 4 is the gate.
    outcome_allowed: bool = True


def _normalized_with_map(text: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed text, plus each output char's index in ``text``."""
    out: list[str] = []
    positions: list[int] = []
    in_space = True  # leading whitespace is dropped, as str.split() would
    for index, char in enumerate(text):
        if char.isspace():
            if not in_space:
                out.append(" ")
                positions.append(index)
            in_space = True
            continue
        out.append(char)
        positions.append(index)
        in_space = False
    while out and out[-1] == " ":
        out.pop()
        positions.pop()
    return "".join(out), positions


def verbatim_span(section_text: str, anchor: str) -> str | None:
    """The exact substring of ``section_text`` that normalizes to ``anchor``.

    The verifier compares quotes whitespace-normalized, so returning the true
    original span (line breaks and all) keeps the citation verbatim under both
    that comparison and a literal one.
    """
    normalized_text, positions = _normalized_with_map(section_text)
    normalized_anchor = " ".join(anchor.split())
    if not normalized_anchor:
        return None
    start = normalized_text.find(normalized_anchor)
    if start < 0:
        return None
    end = start + len(normalized_anchor) - 1
    return section_text[positions[start] : positions[end] + 1]


def decide(
    fact_sheet: FactSheet,
    permit_cfg: PermitTypeConfig | None,
    *,
    corpus_dir: Path,
) -> DecisionResult:
    """Apply the written rules to extracted facts and cite the corpus for it.

    Args:
        fact_sheet: What the extraction agent read out of the application.
        permit_cfg: The permit type's config, or None when it is not
            configured for this office. Used only to report outcome legality.
        corpus_dir: Directory of ``<section>.txt`` files — the same ground
            truth the §7.3 verifier checks citations against.

    Raises:
        UndecidableError: no engaged section has rules, or a rule's quote
            anchor is no longer present in its corpus section.
    """
    engaged = [sid for sid in fact_sheet.section_ids() if sid in SECTIONS]
    if not engaged:
        raise UndecidableError(
            "no rules for the sections this fact sheet engages: "
            f"{fact_sheet.section_ids() or ['(none)']}"
        )

    outcome = rule_for_permit_type(fact_sheet.permit_type)(fact_sheet)

    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for eid in outcome.controlling_element_ids:
        element = element_by_eid(eid)
        if element is None:  # pragma: no cover - registry ids are generated
            continue
        section_file = corpus_dir / f"{element.section_id}.txt"
        if not section_file.exists():
            raise UndecidableError(f"cited section {element.section_id} is not in the corpus")
        span = verbatim_span(section_file.read_text(encoding="utf-8"), element.quote)
        if span is None:
            raise UndecidableError(
                f"{element.provision}: rule quote is no longer a span of "
                f"{element.section_id} - the corpus and the rules have diverged"
            )
        key = (element.section_id, span)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(chunk_id=element.section_id, quote=span))

    if not citations:  # pragma: no cover - a decided outcome always cites
        raise UndecidableError("the rules produced no citable provision")

    return DecisionResult(
        outcome=outcome.outcome,
        citations=citations,
        rationale=outcome.rationale,
        # A rule decision is not a confidence estimate — it is either the
        # written rule applying to stated facts (1.0) or an honest report that
        # a decision-critical element is missing (0.8, per ADR-008).
        confidence=1.0 if outcome.outcome is not DeterminationOutcome.REQUEST_INFO else 0.8,
        controlling_provisions=outcome.controlling_provisions,
        missing_elements=outcome.missing_elements,
        outcome_allowed=permit_cfg is None or outcome.outcome in permit_cfg.allowed_outcomes,
    )


def fact_sheet_from_reply(parsed: dict[str, Any], permit_type: str) -> FactSheet:
    """Build a fact sheet from the extraction agent's JSON reply.

    ``permit_type`` comes from the intake-parsed application, not from the
    reply: the driver already knows it, and a second model guess at a value the
    system holds authoritatively is a second chance to be wrong.
    """
    raw = parsed.get("facts", [])
    facts = [ProvisionFact.model_validate(item) for item in raw] if isinstance(raw, list) else []
    return FactSheet(permit_type=permit_type, facts=facts)


def to_review_finding(result: DecisionResult) -> ReviewFinding:
    """Adapt a rule decision into the §4 contract the verifier already checks.

    The rationale carries the missing elements for a request_info, because the
    verifier's step 5 reads the rationale to test whether the office is asking
    for something the applicant already wrote.
    """
    rationale = result.rationale
    if result.missing_elements:
        rationale = (
            f"{rationale} The application must supply: " + "; ".join(result.missing_elements) + "."
        )
    return ReviewFinding(
        outcome=result.outcome,
        citations=list(result.citations),
        rationale=rationale,
        confidence=result.confidence,
    )
