"""The six-step verification of a review finding (ARCHITECTURE §7.3).

Steps 1 and 2 are deterministic string checks against the committed corpus text —
the same ground truth the citations claim. Step 3 is a structured entailment
check by a cheap model call (injectable for tests). Step 4 checks outcome
legality for the permit type. Step 5 (request_info findings only) rejects
over-asking: a judge must produce a VERBATIM quote of the already-stated
information, and the check fires only when code confirms the quote against the
application — the model proposes, the code enforces. Step 6 (request_info
findings that cleared steps 1-5) rejects a premature request: it asks whether
the stated facts, under the cited provisions, already decide the case. Its
judge is a small Gemma model whose answers are measurably nondeterministic even
at temperature 0, so the check demands TWO independent calls that both say
decidable AND two quotes that this code both machine-verifies against the
application JSON — 2-of-2 agreement plus verbatim confirmation, or the check
does not fire. The report is attached to the determination and persists to the
audit trail; it never silently disappears.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

from civicnexus.contracts import DeterminationOutcome, ReviewFinding
from pydantic import BaseModel, ConfigDict, Field

EntailmentFn = Callable[[str], "EntailmentVerdict"]
OveraskFn = Callable[[str], "OveraskVerdict"]
DecidabilityFn = Callable[[str], "DecidabilityVerdict"]


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


class DecidabilityVerdict(BaseModel):
    """Step 6 answer: do the already-stated facts decide this case on their own?"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decidable: bool
    deciding_quote: str = ""
    # Collected so the judge must commit to a direction, then DISCARDED: it is
    # never read into the retry critique and never reaches the report. Naming an
    # outcome to a retrying reviewer steers it (the 2026-08-28 golden-004 flip).
    decided_outcome_hint: str = ""
    critique: str = ""


class VerifierReport(BaseModel):
    """Outcome of all six §7.3 steps for one finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    sections_exist: bool
    quotes_verbatim: bool
    outcome_entailed: bool
    outcome_legal: bool
    no_overask: bool = True
    no_premature_request: bool = True
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


_DECIDABILITY_PROMPT = """You are a strict verification gate for municipal permit determinations.

The reviewer chose request_info, claiming a decision-critical fact is missing
from the application.

APPLICATION FACTS (JSON):
{application}

REVIEWER RATIONALE (what they say is missing):
{rationale}

CITED PROVISIONS (full section text follows each citation):
{citations_block}

Question: do the facts ALREADY STATED in the application, applied to the cited
provisions, decide this case on their own — with no further information from
the applicant?
- Answer decidable=false unless one stated fact settles the case under the
  cited provisions.
- A hedged or undecided statement ("maybe", "not sure yet", "haven't decided")
  is NOT a stated fact; asking the applicant to resolve a hedge is proper.
- An approximate or relative statement does not settle a numeric or clock-time
  threshold.
- If any element the cited provisions make applicable is still unstated, the
  case is not decided: answer decidable=false.
- If decidable=true, "deciding_quote" MUST be an exact contiguous substring
  copied verbatim from the APPLICATION JSON above (it is machine-checked; a
  paraphrase fails).

Answer as strict JSON with exactly these four keys, and nothing else:
{{"decidable": true/false, "deciding_quote": "verbatim contiguous substring of
the APPLICATION JSON above, or empty", "decided_outcome_hint": "approve or deny
or empty", "critique": "one sentence"}}"""


def _generate_structured[TModel: BaseModel](
    prompt: str, schema: type[TModel], model: str | None = None
) -> TModel:
    """One structured Flash call on the global endpoint (ADR-001 item 8).

    `model` overrides the default MODEL_ID for a single check (step 6 runs a
    different, cheaper judge); passing None keeps the historical behaviour.

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
                model=model or os.environ.get("MODEL_ID", "gemini-3.5-flash"),
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


def _default_decidability(prompt: str) -> DecidabilityVerdict:
    """Step 6's judge, parameterized so a cheaper model can power it.

    response_schema still goes down with the request (via _generate_structured):
    the small judge ignores it and is held to the shape by the prompt text
    instead, while schema-following models keep the stronger guarantee.
    """
    return _generate_structured(
        prompt,
        DecidabilityVerdict,
        os.environ.get("DECIDABILITY_MODEL_ID", "gemma-4-26b-a4b-it-maas"),
    )


def _quote_confirmed(quote: str, application_json: str) -> bool:
    """True when `quote` is a whitespace-normalized contiguous span of the application.

    The model proposes a quote; this is the code that enforces it. A model that
    paraphrases, or invents a fact the applicant never wrote, cannot fail a
    finding on its own say-so.
    """
    normalized = " ".join(quote.split())
    return bool(normalized) and normalized in " ".join(application_json.split())


def verify_finding(
    finding: ReviewFinding,
    *,
    application: dict[str, object],
    permit_allowed_outcomes: list[DeterminationOutcome],
    corpus_dir: Path,
    entailment: EntailmentFn | None = None,
    overask: OveraskFn | None = None,
    decidability: DecidabilityFn | None = None,
) -> VerifierReport:
    """Run all six §7.3 checks; cheap deterministic steps gate the model calls."""
    failures: list[str] = []
    application_json = json.dumps(application, ensure_ascii=False)

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
    # Bound before the branch: step 6 reuses it, and only a reordering bug could
    # ever reach that read with the branch unrun.
    citations_block = ""
    if sections_exist and quotes_verbatim and outcome_legal:
        citations_block = "\n\n".join(
            f"[{c.chunk_id}] quoted: {c.quote!r}\nFULL SECTION:\n{section_texts[c.chunk_id]}"
            for c in finding.citations
        )
        prompt = _ENTAILMENT_PROMPT.format(
            application=application_json,
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
    request_info_verified = (
        finding.outcome is DeterminationOutcome.REQUEST_INFO
        and sections_exist
        and quotes_verbatim
        and outcome_legal
        and outcome_entailed
    )
    if request_info_verified:
        overask_verdict = (overask or _default_overask)(
            _OVERASK_PROMPT.format(application=application_json, rationale=finding.rationale)
        )
        if overask_verdict.already_stated and _quote_confirmed(
            overask_verdict.quote, application_json
        ):
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

    # Step 6 — premature-request check (request_info only), sharing step 5's
    # gate and additionally requiring step 5 to have passed: a finding that is
    # already failing has its critique, and a second judge would buy nothing.
    # Same proposer/enforcer split as step 5, hardened for a small judge that is
    # nondeterministic even at temperature 0 — the check fires only on TWO
    # independent decidable=true answers whose quotes BOTH verify against the
    # application. One dissent, or one unconfirmed quote, and it stays silent.
    no_premature_request = True
    if request_info_verified and no_overask:
        judge = decidability or _default_decidability
        decidability_prompt = _DECIDABILITY_PROMPT.format(
            application=application_json,
            rationale=finding.rationale,
            citations_block=citations_block,
        )
        first = judge(decidability_prompt)
        # Second opinion only when the first says decidable — a "no" already
        # settles the check, and the run should not pay for a rerun of it.
        second = judge(decidability_prompt) if first.decidable else None
        if (
            first.decidable
            and second is not None
            and second.decidable
            and _quote_confirmed(first.deciding_quote, application_json)
            and _quote_confirmed(second.deciding_quote, application_json)
        ):
            no_premature_request = False
            quote = first.deciding_quote
            failures.append(
                f"request_info rejected: the stated facts already decide this "
                f"case - {quote!r} is dispositive under the cited sections"
            )
            # Names the fact, never the outcome: decided_outcome_hint is
            # deliberately not read here, so the retry is pushed off
            # request_info and toward nothing in particular.
            critique = (
                f"The application already states: {quote!r}. Re-apply the "
                f"ordered decision rule: if this stated fact decides the case "
                f"under the cited provisions, decide it; request_info remains "
                f"correct only if a decision-critical fact is genuinely absent "
                f"- name it."
            )

    return VerifierReport(
        passed=sections_exist
        and quotes_verbatim
        and outcome_entailed
        and outcome_legal
        and no_overask
        and no_premature_request,
        sections_exist=sections_exist,
        quotes_verbatim=quotes_verbatim,
        outcome_entailed=outcome_entailed,
        outcome_legal=outcome_legal,
        no_overask=no_overask,
        no_premature_request=no_premature_request,
        failures=failures,
        critique=critique,
    )
