"""The five-step verification of a review finding (ARCHITECTURE §7.3).

Steps 1 and 2 are deterministic string checks against the committed corpus text —
the same ground truth the citations claim. Step 3 is a structured entailment
check by a cheap model call (injectable for tests). Step 4 checks outcome
legality for the permit type. Step 5 (request_info findings only) rejects
over-asking: a judge must produce a VERBATIM quote of the already-stated
information, and the check fires only when code confirms the quote against the
application — the model proposes, the code enforces. The report is attached to
the determination and persists to the audit trail; it never silently disappears.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

from civicnexus.contracts import DeterminationOutcome, ReviewFinding
from pydantic import BaseModel, ConfigDict, Field

EntailmentFn = Callable[[str], "EntailmentVerdict"]
OveraskFn = Callable[[str], "OveraskVerdict"]


class EntailmentVerdict(BaseModel):
    """Structured yes/no from the entailment check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supported: bool
    critique: str


class OveraskVerdict(BaseModel):
    """Step 5 answer: is the requested information already stated?"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    already_stated: bool
    quote: str = ""
    critique: str = ""


class VerifierReport(BaseModel):
    """Outcome of all five §7.3 steps for one finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    sections_exist: bool
    quotes_verbatim: bool
    outcome_entailed: bool
    outcome_legal: bool
    no_overask: bool = True
    failures: list[str] = Field(default_factory=list)
    critique: str = ""

    def as_payload(self) -> dict[str, object]:
        """Shape stored in Determination.verifier_report."""
        return self.model_dump(mode="json")


_ENTAILMENT_PROMPT = """You are a strict verification gate for municipal permit determinations.

APPLICATION FACTS (JSON):
{application}

PROPOSED DETERMINATION: {outcome}
REVIEWER RATIONALE: {rationale}

CITED PROVISIONS (full section text follows each citation):
{citations_block}

Question: do the cited provisions, applied to the application facts as stated,
support the proposed determination?
- For approve: every applicable cited requirement is satisfied by the stated facts.
- For deny: at least one cited provision is unambiguously violated by a stated fact.
- For request_info: something the cited provisions make decision-critical is
  genuinely absent from the stated facts. If the stated facts already decide the
  case either way, request_info is NOT supported.

Answer as strict JSON: {{"supported": true/false, "critique": "one or two sentences;
if unsupported, say exactly what the reviewer got wrong and what the correct
reading is"}}"""


_OVERASK_PROMPT = """You are a strict verification gate for municipal permit determinations.

The reviewer chose request_info, claiming decision-critical information is
missing from the application.

APPLICATION FACTS (JSON):
{application}

REVIEWER RATIONALE (what they say is missing):
{rationale}

Question: does the application ALREADY state the information the reviewer is
requesting?
- A hedged or undecided statement ("maybe", "not sure yet", "haven't decided")
  is NOT stated information — requesting clarification of a hedge is proper.
- Only answer already_stated=true if a specific value or sentence in the
  application answers what the reviewer asked for.
- If already_stated=true, "quote" MUST be an exact contiguous substring copied
  verbatim from the APPLICATION JSON above (it will be machine-checked; a
  paraphrase fails).

Answer as strict JSON: {{"already_stated": true/false, "quote": "verbatim
substring or empty", "critique": "one sentence"}}"""


def _generate_structured[TModel: BaseModel](prompt: str, schema: type[TModel]) -> TModel:
    """One structured Flash call on the global endpoint (ADR-001 item 8).

    ADR-005 §5: bounded transient retry lives HERE and only here (single
    retry layer per failure domain) — a lone 429 must not redden both gated
    metrics of an entire eval run. 4 attempts, jittered backoff.
    """
    import random
    import time

    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(
        vertexai=True,
        project=os.environ.get("PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT", "")),
        location=os.environ.get("MODEL_LOCATION", "global"),
    )
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=os.environ.get("MODEL_ID", "gemini-3.5-flash"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return schema.model_validate(json.loads(response.text or "{}"))
        except Exception as exc:
            message = str(exc)
            if not any(t in message for t in ("429", "503", "500", "UNAVAILABLE", "RESOURCE")):
                raise
            last_exc = exc
            if attempt < 3:
                time.sleep((2**attempt) * 5 + random.uniform(0, 3))
    raise last_exc if last_exc else RuntimeError("structured-call retries exhausted")


def _default_entailment(prompt: str) -> EntailmentVerdict:
    return _generate_structured(prompt, EntailmentVerdict)


def _default_overask(prompt: str) -> OveraskVerdict:
    return _generate_structured(prompt, OveraskVerdict)


def verify_finding(
    finding: ReviewFinding,
    *,
    application: dict[str, object],
    permit_allowed_outcomes: list[DeterminationOutcome],
    corpus_dir: Path,
    entailment: EntailmentFn | None = None,
    overask: OveraskFn | None = None,
) -> VerifierReport:
    """Run all five §7.3 checks; cheap deterministic steps gate the model calls."""
    failures: list[str] = []

    section_texts: dict[str, str] = {}
    sections_exist = True
    for citation in finding.citations:
        section_file = corpus_dir / f"{citation.chunk_id}.txt"
        if not section_file.exists():
            sections_exist = False
            failures.append(f"cited section {citation.chunk_id} does not exist in the corpus")
        else:
            section_texts[citation.chunk_id] = section_file.read_text(encoding="utf-8")

    quotes_verbatim = True
    for citation in finding.citations:
        text = section_texts.get(citation.chunk_id)
        if text is None:
            continue
        if " ".join(citation.quote.split()) not in " ".join(text.split()):
            quotes_verbatim = False
            failures.append(
                f"quote is not a verbatim span of {citation.chunk_id}: {citation.quote[:60]!r}"
            )

    outcome_legal = finding.outcome in permit_allowed_outcomes
    if not outcome_legal:
        if not permit_allowed_outcomes:
            # Unknown permit type: NO outcome can pass. Say that honestly —
            # the old "outcome X is not allowed" wording read as "pick a
            # different outcome" and measurably flipped a correct request_info
            # to a wrong approve on retry (2026-08-28, golden-004).
            failures.append(
                "permit type is not configured for this office - no outcome can "
                "be verified as legal; an out-of-scope request escalates to a human"
            )
        else:
            failures.append(f"outcome {finding.outcome.value} is not allowed for this permit type")

    outcome_entailed = False
    if sections_exist and quotes_verbatim and outcome_legal:
        citations_block = "\n\n".join(
            f"[{c.chunk_id}] quoted: {c.quote!r}\nFULL SECTION:\n{section_texts[c.chunk_id]}"
            for c in finding.citations
        )
        prompt = _ENTAILMENT_PROMPT.format(
            application=json.dumps(application, ensure_ascii=False),
            outcome=finding.outcome.value,
            rationale=finding.rationale,
            citations_block=citations_block,
        )
        verdict = (entailment or _default_entailment)(prompt)
        outcome_entailed = verdict.supported
        if not verdict.supported:
            failures.append(f"entailment: {verdict.critique}")
        critique = verdict.critique
    else:
        critique = "; ".join(failures)

    # Step 5 — over-ask legality (request_info only), gated on steps 1-4 so a
    # finding never pays two model calls when it is already failing. The check
    # fires ONLY on a machine-confirmed verbatim quote: the judge proposes,
    # this code verifies the quote against the application the reviewer saw.
    no_overask = True
    if (
        finding.outcome is DeterminationOutcome.REQUEST_INFO
        and sections_exist
        and quotes_verbatim
        and outcome_legal
        and outcome_entailed
    ):
        application_json = json.dumps(application, ensure_ascii=False)
        overask_verdict = (overask or _default_overask)(
            _OVERASK_PROMPT.format(application=application_json, rationale=finding.rationale)
        )
        quote_normalized = " ".join(overask_verdict.quote.split())
        quote_confirmed = bool(quote_normalized) and quote_normalized in " ".join(
            application_json.split()
        )
        if overask_verdict.already_stated and quote_confirmed:
            no_overask = False
            failures.append(
                f"over-ask: the application already states the requested "
                f"information: {overask_verdict.quote!r}"
            )
            critique = (
                f"Your request_info is rejected: the application already states "
                f"{overask_verdict.quote!r}. Re-apply the decision rule treating this "
                f"as a stated fact and decide; request_info remains correct only if "
                f"some OTHER decision-critical fact is genuinely absent — name it."
            )

    return VerifierReport(
        passed=sections_exist
        and quotes_verbatim
        and outcome_entailed
        and outcome_legal
        and no_overask,
        sections_exist=sections_exist,
        quotes_verbatim=quotes_verbatim,
        outcome_entailed=outcome_entailed,
        outcome_legal=outcome_legal,
        no_overask=no_overask,
        failures=failures,
        critique=critique,
    )
