"""The fact sheet: what the model is allowed to produce, and nothing more.

The measured failure this package answers (B-006, PROGRESS "Accuracy levers")
is decision nondeterminism, not retrieval: five full PermitBench runs at
temperature 0 scored 80/70/80/65/70 percent, and "4 of 5 misses had CORRECT
citations". The model was reading the law correctly and then composing the
outcome differently from one run to the next.

So the model's job shrinks to what it is reliably good at — reading an
application and reporting, per statute element, what the applicant said — and
the composition step moves into :mod:`civicnexus.decision.rules`, which is
ordinary Python and therefore identical on every run.

A ``ProvisionFact`` carries no conclusion. ``status`` is a report about the
application text, ``stated_value`` is the value the applicant gave for that one
element (not the whole sentence), and ``quote`` is the verbatim span the value
came from so the claim stays auditable.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FactStatus(StrEnum):
    """What the application says about one statute element.

    The four values are the exact literals the extraction schema allows.

    SATISFIED
        The application states something that meets the element.
    VIOLATED
        The application states something that fails the element. For a
        negatively-phrased trigger element ("no late-night operation"),
        ``violated`` means the triggering condition IS present — it does not
        by itself mean the application is denied; see
        :class:`~civicnexus.decision.rules.ElementKind`.
    HEDGED
        The applicant addressed the element but left it undecided or stated it
        only relatively ("maybe", "haven't decided", "well before sunrise").
    ABSENT
        The application says nothing about the element.
    """

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    HEDGED = "hedged"
    ABSENT = "absent"


class ProvisionFact(BaseModel):
    """One statute element, as reported against one application."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Statute division, e.g. ``"17.44.100(G)"`` or ``"17.44.104(F)(3)"``.
    provision: str
    #: Element key from the rule registry, e.g. ``"rooms_used"``.
    element: str
    status: FactStatus
    #: The value the applicant gave for THIS element ("two bedrooms", "55
    #: feet", "well before sunrise") — not the surrounding sentence. The rule
    #: layer parses it and overrides ``status`` when it yields a number, so a
    #: value scoped to some other element would corrupt the comparison.
    stated_value: str = ""
    #: Verbatim span from the application the value was read from.
    quote: str = ""

    @property
    def section_id(self) -> str:
        """Corpus chunk id — the provision with its divisions stripped."""
        return self.provision.split("(", 1)[0].strip()


class FactSheet(BaseModel):
    """Every element the extractor engaged for one application."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    permit_type: str
    facts: list[ProvisionFact] = Field(default_factory=list)

    def section_ids(self) -> list[str]:
        """Sections the extractor engaged, in first-seen order.

        Section-level applicability is an extraction judgment (which sections
        retrieval returned and the reader engaged); element-level applicability
        inside a section belongs to the rules. ADR-008 records that split.
        """
        seen: list[str] = []
        for fact in self.facts:
            if fact.section_id not in seen:
                seen.append(fact.section_id)
        return seen

    def get(self, provision: str) -> ProvisionFact | None:
        """The fact reported for ``provision``, or None if it was not reported."""
        for fact in self.facts:
            if fact.provision == provision:
                return fact
        return None

    def get_by_element(self, eid: str) -> ProvisionFact | None:
        """The fact for a ``"<section>/<element key>"`` id from the rule registry.

        Element key, not provision, is the join between extractor and rules:
        one provision can impose several elements (§17.44.070(A) sets four
        setbacks in a single sentence), so the provision alone is ambiguous.
        """
        section_id, _, key = eid.partition("/")
        for fact in self.facts:
            if fact.section_id == section_id and fact.element == key:
                return fact
        return None

    def for_section(self, section_id: str) -> list[ProvisionFact]:
        """Every fact reported against one corpus section."""
        return [fact for fact in self.facts if fact.section_id == section_id]
