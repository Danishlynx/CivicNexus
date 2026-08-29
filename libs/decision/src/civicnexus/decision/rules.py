"""The statute, written as code.

This module holds three things the model used to hold in its head, and got
wrong differently on different runs:

1. **The checklist.** Which elements each section imposes. The extractor cannot
   shorten it and cannot pad it — over-asking (golden-010/013/020) and
   over-deciding (golden-008/014) were both failures of an implicit checklist.
2. **Applicability.** Which elements are live given the other facts:
   specific-controls-general (§17.44.030 over §17.44.100(F)/(G)), the
   §17.44.200 savings clause, and the §17.44.103 late-night triggers.
3. **Composition.** The ordered rule that turns element statuses into one
   outcome.

Element classification follows one criterion, applied to the statute text:

``PROHIBITION``
    A development standard or a bar on conduct. A stated fact outside it is a
    violation; silence about it is not — asking anyway is the over-ask the
    §7.3 verifier's step 5 exists to catch.
``THRESHOLD``
    An eligibility precondition or a required application content ("the
    application shall include..."). The applicant must establish it, so
    silence IS decision-critical.
``TRIGGER``
    A condition that switches other elements on. Phrased negatively, so
    ``satisfied`` means the condition is excluded and the dependants go quiet;
    ``violated`` means it is present and they wake up. A fired trigger is
    never by itself a denial.

The rules never see the model's opinion of the outcome — only per-element
statuses, values and quotes. Where a stated value yields a number, the code
recomputes the status and overrides the extractor outright.
"""

import re
from collections.abc import Callable
from enum import StrEnum

from civicnexus.contracts import DeterminationOutcome
from civicnexus.decision.facts import FactSheet, FactStatus, ProvisionFact
from pydantic import BaseModel, ConfigDict, Field


class ElementKind(StrEnum):
    """How one statute element behaves when the application is silent."""

    PROHIBITION = "prohibition"
    THRESHOLD = "threshold"
    TRIGGER = "trigger"


class Comparator(StrEnum):
    """Direction of a numeric bound."""

    AT_MOST = "at_most"
    AT_LEAST = "at_least"


class Bound(BaseModel):
    """A numeric or clock-window limit the code evaluates itself."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparator: Comparator = Comparator.AT_MOST
    value: float = 0.0
    #: One of the keys of :data:`_UNIT_PATTERNS`, or ``"clock"``.
    unit: str = "clock"
    #: When set, the limit is read from another element's stated value instead
    #: of ``value`` — §17.44.215(B)(2) sets the setback to the system height.
    value_from: str = ""
    #: Clock window, minutes from midnight, half-open [start, end).
    window_start_min: int = 0
    window_end_min: int = 0


class ZoneRule(BaseModel):
    """Zone eligibility the code adjudicates from the stated zone token."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    permitted: frozenset[str] = frozenset()
    #: Allowed subject to a conditional use permit — a process step, not a bar.
    conditional: frozenset[str] = frozenset()
    #: Zones where the use is barred outright.
    forbidden: frozenset[str] = frozenset()


class Element(BaseModel):
    """One requirement of one statute section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provision: str
    key: str
    kind: ElementKind
    #: What a request_info must name if this element is unresolved.
    summary: str
    #: A verbatim span of the section, used directly as the citation quote.
    #: ``tests/test_rules_golden.py`` asserts every one resolves uniquely.
    quote: str
    bound: Bound | None = None
    zone_rule: ZoneRule | None = None
    #: ``"<section>/<key>"`` ids. This element is live when ANY of them is
    #: fired (violated) or unresolved (hedged/absent); it goes quiet only when
    #: every one of them is satisfied.
    requires: tuple[str, ...] = ()

    @property
    def eid(self) -> str:
        """Stable id used by :attr:`requires`."""
        return f"{self.section_id}/{self.key}"

    @property
    def section_id(self) -> str:
        return self.provision.split("(", 1)[0].strip()


class Section(BaseModel):
    """One corpus section's full element checklist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str
    title: str
    elements: tuple[Element, ...]


class Suppression(BaseModel):
    """A specific provision displacing a general one (ADR-008).

    Recorded as data, not as a branch, so the audit trail can say which
    specific provision displaced which general one and why.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    suppressed_provision: str
    controlling_provision: str
    when_section_present: str
    reason: str


class ElementVerdict(BaseModel):
    """One element after the code has evaluated it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    element: Element
    status: FactStatus
    applicable: bool
    reason: str = ""
    fact: ProvisionFact | None = None


class RuleOutcome(BaseModel):
    """What a per-permit-type rule function returns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: DeterminationOutcome
    controlling_provisions: list[str] = Field(default_factory=list)
    rationale: str = ""
    #: Element summaries a request_info must ask for, in section order.
    missing_elements: list[str] = Field(default_factory=list)
    #: ``"<section>/<key>"`` ids of the elements that carried the decision.
    #: Citations are built from these, because one provision string can cover
    #: several elements and would not identify the quote to cite.
    controlling_element_ids: list[str] = Field(default_factory=list)
    verdicts: list[ElementVerdict] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Value parsing. The code owns every comparison it can make for itself.
# --------------------------------------------------------------------------

_WORD_NUMBERS = {
    "zero": 0.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
    "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0,
    "eleven": 11.0, "twelve": 12.0, "thirteen": 13.0, "fourteen": 14.0,
    "fifteen": 15.0, "sixteen": 16.0, "seventeen": 17.0, "eighteen": 18.0,
    "nineteen": 19.0, "twenty": 20.0,
}  # fmt: skip

_NUM = r"(?:\d[\d,]*(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")"

#: unit key -> ((unit token regex, multiplier to the canonical unit), ...).
#: Longer/compound units are listed before the plain one so "square feet"
#: cannot be read as "feet"; a match must anchor on the number itself, so
#: "800 square feet" never yields 800 for the "feet" unit.
_UNIT_PATTERNS: dict[str, tuple[tuple[str, float], ...]] = {
    "square_feet": ((r"square\s+f(?:ee|oo)t", 1.0), (r"sq\.?\s*ft\.?", 1.0), (r"sf", 1.0)),
    "feet": ((r"f(?:ee|oo)t", 1.0), (r"ft\.?", 1.0), (r"in(?:ches|ch)?\.?", 1.0 / 12.0)),
    "acres": ((r"acres?", 1.0),),
    "rooms": ((r"rooms?", 1.0), (r"bedrooms?", 1.0)),
    "bedrooms": ((r"bedrooms?", 1.0),),
    "plants": ((r"plants?", 1.0),),
    "decibels": ((r"decibels?", 1.0), (r"dba?", 1.0)),
}

#: Phrases that make a statement relative or approximate. Mirrors the §7.3
#: step-6 prompt: "An approximate or relative statement does not settle a
#: numeric or clock-time threshold." Applied ONLY when no number was parsed —
#: "about 3 feet" carries a number and is decided on the number.
_APPROX_MARKERS = (
    r"about",
    r"approximate(?:ly)?",
    r"roughly",
    r"around",
    r"maybe",
    r"perhaps",
    r"unsure",
    r"not\s+sure",
    r"have\s?n'?t\s+decided",
    r"have\s+not\s+decided",
    r"undecided",
    r"or\s+so",
    r"a\s+few",
    r"several",
    r"some",
    r"give\s+or\s+take",
    r"sunrise",
    r"sunset",
    r"sundown",
    r"dawn",
    r"pre-?dawn",
    r"dusk",
    r"daybreak",
    r"early",
    r"late",
    r"nearby",
    r"close\s+to",
    r"down\s+the\s+block",
    r"houses\s+down",
    r"doors\s+down",
    r"next\s+door",
    r"well\s+before",
)
_APPROX_RE = re.compile(r"\b(?:" + "|".join(_APPROX_MARKERS) + r")\b", re.IGNORECASE)

_CLOCK_RE = re.compile(
    r"\b(?:(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)|(\d{1,2}):(\d{2})|(midnight)|(noon))\b",
    re.IGNORECASE,
)

# Case is the signal: zone designators are written uppercase ("RL", "R-1",
# "C-R/S") and the prose around them is not, so the pattern is applied to the
# value as written. The trailing guard rejects the capital of an ordinary
# capitalised word ("The", "Theodore").
_ZONE_RE = re.compile(r"\b([A-Z][A-Z0-9]{0,5}(?:[-/][A-Z0-9]{1,4})*)\b(?![a-z])")


def _to_number(token: str) -> float:
    lowered = token.strip().lower().replace(",", "")
    if lowered in _WORD_NUMBERS:
        return _WORD_NUMBERS[lowered]
    return float(lowered)


def parse_quantity(stated_value: str, unit: str) -> float | None:
    """The single quantity ``stated_value`` gives in ``unit``, or None.

    Deliberately conservative: zero matches means the code has nothing to
    decide on, and MORE than one match means the value is ambiguous ("four
    bedrooms and we rent two"), which is not something code should adjudicate
    silently. Both fall back to the extractor's status.
    """
    patterns = _UNIT_PATTERNS.get(unit)
    if patterns is None:
        return None
    found: list[float] = []
    for token_re, multiplier in patterns:
        for match in re.finditer(
            rf"\b({_NUM})\s*-?\s*(?:{token_re})\b", stated_value, re.IGNORECASE
        ):
            found.append(_to_number(match.group(1)) * multiplier)
    return found[0] if len(found) == 1 else None


def parse_clock_minutes(stated_value: str) -> int | None:
    """The single clock time in ``stated_value`` as minutes from midnight."""
    found: list[int] = []
    for match in _CLOCK_RE.finditer(stated_value):
        if match.group(6):
            found.append(0)
            continue
        if match.group(7):
            found.append(12 * 60)
            continue
        if match.group(4):
            found.append(int(match.group(4)) % 24 * 60 + int(match.group(5)))
            continue
        hour = int(match.group(1)) % 12
        minute = int(match.group(2) or 0)
        if match.group(3).lower().startswith("p"):
            hour += 12
        found.append(hour * 60 + minute)
    return found[0] if len(found) == 1 else None


def is_approximate(stated_value: str) -> bool:
    """True when the value is relative or approximate rather than quantified."""
    return bool(_APPROX_RE.search(stated_value))


def _normalize_zone(token: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", token.upper())


def parse_zone(stated_value: str) -> str | None:
    """The zone token stated, normalized ("R-1" -> "R1", "C-R/S" -> "CRS").

    Conservative in the same way as :func:`parse_quantity`: two candidate
    tokens means the value is ambiguous, and the code declines to classify it.
    """
    candidates = _dedupe(
        [
            _normalize_zone(match.group(1))
            for match in _ZONE_RE.finditer(stated_value)
            if 0 < len(_normalize_zone(match.group(1))) <= 6
        ]
    )
    return candidates[0] if len(candidates) == 1 else None


# --------------------------------------------------------------------------
# Zone vocabulary, read off the corpus.
# --------------------------------------------------------------------------

#: §17.44.070 names the residential zones ("permitted use in the RF, RE, RL, RM
#: and RH zones") against the non-residential ones ("NC, C-R/S, O/RD/LM, M, and
#: P/QP"). R1 is not in the corpus text; it appears in the golden-018 fixture
#: as "zoned R-1" and is classed residential here on its ordinary meaning
#: (recorded as an ambiguity in ADR-008, and load-bearing for nothing: 018
#: turns on R-1 being outside {M, PD}, not on it being residential).
RESIDENTIAL_ZONES = frozenset({"RF", "RE", "RL", "RM", "RH", "R1", "R2", "R3"})
NONRESIDENTIAL_ZONES = frozenset({"NC", "CRS", "ORDLM", "M", "PQP", "BE", "PD"})


# --------------------------------------------------------------------------
# The registry.
# --------------------------------------------------------------------------


def _e(
    provision: str,
    key: str,
    kind: ElementKind,
    summary: str,
    quote: str,
    *,
    bound: Bound | None = None,
    zone_rule: ZoneRule | None = None,
    requires: tuple[str, ...] = (),
) -> Element:
    return Element(
        provision=provision,
        key=key,
        kind=kind,
        summary=summary,
        quote=quote,
        bound=bound,
        zone_rule=zone_rule,
        requires=requires,
    )


P = ElementKind.PROHIBITION
T = ElementKind.THRESHOLD
G = ElementKind.TRIGGER

_HOME_OCCUPATION = Section(
    section_id="17.44.100",
    title="Home occupations",
    elements=(
        _e(
            "17.44.100(A)",
            "no_nonresident_employees",
            P,
            "whether anyone other than a member of the resident family works in the occupation",
            "No employees are allowed other than members of the resident family",
        ),
        _e(
            "17.44.100(B)",
            "normal_materials_and_equipment",
            P,
            "whether the materials or equipment used are normal to the zone",
            "No use of material or equipment not recognized as being part of the normal "
            "practices in the zone in which the use is a part is allowed",
        ),
        _e(
            "17.44.100(C)",
            "no_excess_traffic",
            P,
            "whether the use generates pedestrian or vehicular traffic beyond that normal "
            "to the zone",
            "The use shall not generate pedestrian or vehicular traffic beyond that normal "
            "to the zone in which it is located",
        ),
        _e(
            "17.44.100(D)",
            "no_commercial_delivery_vehicles",
            P,
            "whether commercial vehicles deliver materials to or from the premises",
            "It shall not involve the use of commercial vehicles for delivery of materials "
            "to or from the premises for commercial purposes",
        ),
        _e(
            "17.44.100(E)",
            "no_outside_storage",
            P,
            "whether materials or supplies are stored outside",
            "No outside storage of materials and/or supplies is allowed",
        ),
        _e(
            "17.44.100(F)",
            "no_nonresidential_signs",
            P,
            "whether a sign other than one permitted for a residential use is proposed",
            "It shall not involve the use of signs other than those permitted for a "
            "residential use",
        ),
        _e(
            "17.44.100(G)",
            "rooms_used",
            P,
            "confirmation that the occupation will be confined to not more than one room",
            "Not more than one room in a dwelling or in an accessory structure shall be "
            "employed for the home occupation",
            bound=Bound(comparator=Comparator.AT_MOST, value=1, unit="rooms"),
        ),
        _e(
            "17.44.100(H)",
            "appearance_stays_residential",
            P,
            "whether the structure's appearance or the conduct of the occupation would make "
            "it recognizable as a nonresidential use",
            "In no way shall the appearance of the structure be so altered or the conduct of "
            "the occupation within the structure be such that the structure be reasonably "
            "recognized as serving a nonresidential use",
        ),
        _e(
            "17.44.100(I)",
            "normal_utility_use",
            P,
            "whether utilities or community facilities are used beyond normal residential use",
            "There shall be no use of utilities or community facilities beyond that normal to "
            "the use of the property for residential purposes",
        ),
    ),
)

_BED_AND_BREAKFAST = Section(
    section_id="17.44.030",
    title="Bed and breakfast homes",
    elements=(
        _e(
            "17.44.030(A)",
            "minimum_floor_area",
            T,
            "Total residential floor area of the building in square feet, to verify the "
            "2,000 sq ft minimum in 17.44.030(A)",
            "having a minimum of 2,000 square feet of residential floor area",
            bound=Bound(comparator=Comparator.AT_LEAST, value=2000, unit="square_feet"),
        ),
        _e(
            "17.44.030(B)",
            "rented_bedrooms",
            P,
            "the number of bedrooms to be rented, against the 50%/three-bedroom cap",
            "Fifty percent of the bedrooms in a home can be used for rental to a maximum "
            "number of three bedrooms",
            bound=Bound(comparator=Comparator.AT_MOST, value=3, unit="bedrooms"),
        ),
        _e(
            "17.44.030(C)",
            "owner_occupied",
            T,
            "whether the property is the principal residence of the owner",
            "The property must be the principal residence of the owner",
        ),
        _e(
            "17.44.030(D)",
            "sign_within_limits",
            P,
            "the type and size of the proposed on-premise sign",
            "On-premise signs for any bed and breakfast home shall be limited to one wall "
            "or hanging wood sign not more than 12 inches by 36 inches",
        ),
        _e(
            "17.44.030(E)",
            "no_guest_room_cooking",
            P,
            "whether cooking facilities are proposed in any guest room",
            "No cooking facilities shall be permitted in any guest room",
        ),
        _e(
            "17.44.030(F)",
            "meals_limited",
            P,
            "which meals are served and to whom",
            "No meals shall be served to guests other than breakfast",
        ),
        _e(
            "17.44.030(G)",
            "occupancy_length",
            P,
            "the length of guest stays",
            "No guest shall be permitted to rent accommodations or remain in occupancy for "
            "a period in excess of 14 days during any consecutive 90-day period",
        ),
        _e(
            "17.44.030(H)",
            "required_parking",
            T,
            "Number of existing off-street parking spaces on the site, to verify the home has "
            "the currently required parking under 17.44.030(H)",
            "The existing home must have the current required parking",
        ),
        _e(
            "17.44.030(I)",
            "guest_register",
            P,
            "whether a guest register will be kept",
            "shall at all times keep and maintain therein a register",
        ),
    ),
)

_GAME_COURTS = Section(
    section_id="17.44.070",
    title="Game courts",
    elements=(
        _e(
            "17.44.070",
            "permitted_zone",
            T,
            "the zoning designation of the property",
            "Game courts shall be a permitted use in the RF, RE, RL, RM and RH zones",
            zone_rule=ZoneRule(
                permitted=frozenset({"RF", "RE", "RL", "RM", "RH"}),
                conditional=frozenset({"NC", "CRS", "ORDLM", "M", "PQP"}),
            ),
        ),
        _e(
            "17.44.070(A)",
            "side_yard_setback_interior_lot",
            P,
            "the interior side yard setback, against the five-foot minimum",
            "side yard setback, interior lot, shall be a minimum of five feet",
            bound=Bound(comparator=Comparator.AT_LEAST, value=5, unit="feet"),
        ),
        _e(
            "17.44.070(A)",
            "alley_side_setback",
            P,
            "the alley-side setback",
            "alley-side setback may be zero feet",
            bound=Bound(comparator=Comparator.AT_LEAST, value=0, unit="feet"),
        ),
        _e(
            "17.44.070(A)",
            "street_yard_setback",
            P,
            "the street yard setback, against the ten-foot minimum",
            "street yard setback shall be a minimum of ten feet",
            bound=Bound(comparator=Comparator.AT_LEAST, value=10, unit="feet"),
        ),
        _e(
            "17.44.070(B)",
            "lighting",
            P,
            "the proposed game court lighting",
            "Game court lighting shall be subject to the requirements set forth in Chapter 17.32",
        ),
        _e(
            "17.44.070(C)",
            "fencing_and_landscaping",
            P,
            "the proposed fencing and landscaping",
            "Game court fencing/landscaping shall be subject to the requirements set forth in "
            "Chapters 17.08 and 17.12",
        ),
    ),
)

_LATE_NIGHT = Section(
    section_id="17.44.103",
    title="Late-night business operations",
    elements=(
        _e(
            "17.44.103(B)",
            "no_late_night_operation",
            G,
            "The exact daily start time of business activity - specifically whether any "
            "operation occurs between 12:00 midnight and 6:00 a.m., which is the definition "
            "of late-night hours in 17.44.103(B)",
            "LATE-NIGHT HOURS shall mean any business that operates anytime between the "
            "hours of 12:00 midnight and 6:00 a.m.",
            bound=Bound(unit="clock", window_start_min=0, window_end_min=360),
        ),
        _e(
            "17.44.103(C)",
            "not_within_100ft_of_residential_zone",
            G,
            "Confirmation of the parcel's zoning and the distance from all property lines of "
            "the subject property to the nearest residential zone or planned development zone "
            "permitting residential uses, to determine whether the 100-foot conditional use "
            "permit trigger in 17.44.103(C) applies",
            "located within 100 feet of any residential zone or planned development zone "
            "permitting residential uses as measured from all property lines of the subject "
            "property",
            bound=Bound(comparator=Comparator.AT_LEAST, value=100, unit="feet"),
            requires=("17.44.103/no_late_night_operation",),
        ),
        _e(
            "17.44.103(C)",
            "conditional_use_permit",
            T,
            "evidence of the conditional use permit required by 17.44.103(C), or confirmation "
            "that the late-night and 100-foot triggers do not apply",
            "shall obtain a conditional use permit from the Planning Commission",
            requires=("17.44.103/not_within_100ft_of_residential_zone",),
        ),
    ),
)

_CANNABIS = Section(
    section_id="17.44.104",
    title="Commercial cannabis uses and cultivation",
    # (C)(3) bars indoor cultivation "except in strict compliance with division
    # (F)". (F) is therefore an exception the applicant must establish, so every
    # standard is a THRESHOLD, not a prohibition — the strictest available
    # reading. golden-013 still approves under it, because the applicant stated
    # all eleven.
    elements=(
        _e(
            "17.44.104(F)(1)",
            "cultivator_over_21_and_secured_from_minors",
            T,
            "whether the cultivator is at least 21 and the cultivation area is inaccessible "
            "to persons under 21",
            "Only a person who is at least 21 years old may cultivate cannabis, and the "
            "cannabis cultivation areas shall not be accessible to persons under 21 years of age",
        ),
        _e(
            "17.44.104(F)(2)",
            "fully_enclosed_and_secure_structure",
            T,
            "whether cultivation is within a fully enclosed and secure structure",
            "Cannabis cultivation is permitted only within fully enclosed and secure structures",
        ),
        _e(
            "17.44.104(F)(3)",
            "plant_count",
            T,
            "the total number of cannabis plants, against the six-plant cap",
            "Cannabis cultivation shall be limited to six plants total",
            bound=Bound(comparator=Comparator.AT_MOST, value=6, unit="plants"),
        ),
        _e(
            "17.44.104(F)(4)",
            "no_co2_or_ozone_generators",
            T,
            "whether CO2 or ozone generators are used",
            "The use of CO2 and Ozone generators for cannabis cultivation or processing is "
            "prohibited",
        ),
        _e(
            "17.44.104(F)(5)",
            "no_compressed_gases",
            T,
            "whether compressed gases are used",
            "The use of compressed gases, including but not limited to carbon dioxide and "
            "butane, for cultivation or processing is prohibited",
        ),
        _e(
            "17.44.104(F)(6)",
            "not_visible_from_public_right_of_way",
            T,
            "whether the cultivation is visible from the public right-of-way",
            "Cannabis cultivation shall not be visible from the public right-of-way",
        ),
        _e(
            "17.44.104(F)(7)",
            "dwelling_remains_a_residence",
            T,
            "whether the dwelling remains a residence with functioning cooking, sleeping and "
            "sanitation facilities",
            "The dwelling shall remain at all times a residence, with legal and functioning "
            "cooking, sleeping and sanitation facilities with proper ingress and egress",
        ),
        _e(
            "17.44.104(F)(8)",
            "no_public_nuisance",
            T,
            "whether odor, light, noise or other effects would reach adjacent property",
            "shall not become a public nuisance to surrounding properties or the public",
        ),
        _e(
            "17.44.104(F)(9)",
            "fire_extinguisher_in_residence",
            T,
            "whether a portable fire extinguisher is kept in the residence",
            "A portable fully functional fire extinguisher",
        ),
        _e(
            "17.44.104(F)(10)",
            "does_not_displace_parking",
            T,
            "whether the cultivation displaces required off-street parking",
            "Cultivation of cannabis shall not displace required off-street parking",
        ),
        _e(
            "17.44.104(F)(11)",
            "electrical_directly_connected",
            T,
            "how the cultivation equipment is electrically connected",
            "All electrical equipment used in the cultivation of cannabis",
        ),
    ),
)

_SAVINGS_CLAUSE_SECTION = "17.44.200"
_PUBLIC_PROJECT_STORAGE = Section(
    section_id=_SAVINGS_CLAUSE_SECTION,
    title="Temporary storage of equipment and supplies for public projects",
    elements=(
        _e(
            "17.44.200",
            "temporary_occupation_for_storage",
            T,
            "whether the occupation of land is temporary and for storage of vehicles, "
            "supplies or materials",
            "the temporary occupation of land for the storage of vehicles, supplies, "
            "materials or related items",
        ),
        _e(
            "17.44.200",
            "public_project_nexus",
            T,
            "the public construction, installation, repair or maintenance project the storage "
            "is connected to",
            "in connection with the construction or reconstruction, installation, demolition, "
            "repair of maintenance of streets",
        ),
        _e(
            "17.44.200",
            "landowner_consent",
            T,
            "the consent of the person owning, occupying or controlling the land",
            "provided that the consent of person owning, occupying, or having control of the "
            "land is obtained",
        ),
        _e(
            "17.44.200",
            "council_permission_for_stated_time",
            T,
            "the Council's permission and the stated limited time it was granted for",
            "the Council first grants its permission for a stated limited time",
        ),
    ),
)

_ADU = Section(
    section_id="17.44.005",
    title="Accessory dwelling units and junior accessory dwelling units",
    elements=(
        _e(
            "17.44.005(B)(1)",
            "primary_dwelling_on_lot",
            T,
            "whether the lot has an existing or proposed single-family or multi-family "
            "dwelling structure",
            "ADUs shall be permitted on lots developed with an existing or proposed "
            "single-family dwelling structure",
        ),
        _e(
            "17.44.005(D)(1)(a)2.c.",
            "conversion_expansion_square_feet",
            P,
            "the floor area added beyond the existing accessory structure, against the "
            "150 sq ft cap",
            "it may include an expansion of not more than 150 square feet beyond the same "
            "physical dimensions as the existing accessory structure",
            bound=Bound(comparator=Comparator.AT_MOST, value=150, unit="square_feet"),
        ),
        _e(
            "17.44.005(D)(1)(b)1.b.",
            "new_detached_adu_square_feet",
            P,
            "the floor area of the new detached ADU, against the 800 sq ft cap",
            "The maximum size of the ADU is 800 square feet.",
            bound=Bound(comparator=Comparator.AT_MOST, value=800, unit="square_feet"),
        ),
        _e(
            "17.44.005(D)(1)(b)3.",
            "detached_adu_height",
            P,
            "the height of the ADU, against the 16-foot limit",
            "The ADU shall be no more than 16 feet in height, except as follows",
            bound=Bound(comparator=Comparator.AT_MOST, value=16, unit="feet"),
        ),
        _e(
            "17.44.005(E)(3)(a)",
            "side_and_rear_setback",
            P,
            "the side and rear setbacks, against the four-foot minimum",
            "Four feet for newly constructed attached and detached ADUs and additions beyond "
            "the existing footprint",
            bound=Bound(comparator=Comparator.AT_LEAST, value=4, unit="feet"),
        ),
        _e(
            "17.44.005(G)(1)",
            "rental_term",
            P,
            "the rental term proposed for the unit",
            "All rental ADUs shall be rented for 30 consecutive days or more",
        ),
    ),
)

_LARGE_DAY_CARE = Section(
    section_id="17.44.060",
    title="Family day care home (large)",
    elements=(
        _e(
            "17.44.060(B)",
            "hours_of_operation",
            P,
            "the proposed hours of operation, against the 7:00 a.m. to 7:00 p.m. standard",
            "Hours of operation shall be between 7:00 a.m. and 7:00 p.m.",
        ),
        _e(
            "17.44.060(C)",
            "no_other_day_care_facility_nearby",
            G,
            "whether any other day care facility operates in the vicinity",
            "There shall be no more than one large family day care permitted within a radius "
            "of 1,000 feet of any other such facility",
        ),
        _e(
            "17.44.060(C)",
            "other_facility_is_not_a_large_family_day_care",
            G,
            "Whether the other day care two houses down is licensed/permitted as a large "
            "family day care home (as opposed to a small family day care home) - the "
            "1,000-foot rule in 17.44.060(C) only counts 'any other such facility', i.e. "
            "another large family day care",
            "within a radius of 1,000 feet of any other such facility",
            requires=("17.44.060/no_other_day_care_facility_nearby",),
        ),
        _e(
            "17.44.060(C)",
            "not_within_1000ft_of_other_large_facility",
            G,
            "The distance between the applicant's site and that other facility, i.e. whether "
            "it falls inside the 1,000-foot radius",
            "no more than one large family day care permitted within a radius of 1,000 feet",
            bound=Bound(comparator=Comparator.AT_LEAST, value=1000, unit="feet"),
            requires=("17.44.060/other_facility_is_not_a_large_family_day_care",),
        ),
        _e(
            "17.44.060(C)",
            "adverse_impact_showing",
            T,
            "If it is a large family day care within 1,000 feet: the applicant's showing that "
            "a second such facility would not have an adverse impact on the neighborhood, "
            "which is the only basis on which the Committee may permit it",
            "The Committee may permit more than one such facility within a 1,000-foot radius, "
            "provided that it can be determined that it would not have an adverse impact to "
            "the neighborhood",
            requires=("17.44.060/not_within_1000ft_of_other_large_facility",),
        ),
    ),
)

_GASOLINE_TANKS = Section(
    section_id="17.44.080",
    title="Gasoline pumps, dispensers and storage tanks",
    elements=(
        _e(
            "17.44.080",
            "no_above_ground_tank_outside_buildings",
            G,
            "whether an above-ground tank for flammable liquids outside a building is proposed",
            "above-ground tanks outside of buildings for the storage of flammable liquids",
        ),
        _e(
            "17.44.080",
            "tank_not_in_residential_zone",
            P,
            "the zoning designation of the property",
            "Above-ground tanks shall be prohibited in residential zones",
            zone_rule=ZoneRule(forbidden=RESIDENTIAL_ZONES),
            requires=("17.44.080/no_above_ground_tank_outside_buildings",),
        ),
    ),
)

_TRANSMITTING_ANTENNAE = Section(
    section_id="17.44.120",
    title="Private transmitting antennae",
    elements=(
        _e(
            "17.44.120(C)(1)",
            "antenna_total_height",
            T,
            "Total height of the mast and antenna above grade, including the beam at its "
            "highest point",
            "The antennae shall have a reasonable relationship with the height and massing of "
            "the main building on the site",
        ),
        _e(
            "17.44.120(C)(1)",
            "main_building_height_and_massing",
            T,
            "Height and massing of the main building on the site, so the (C)(1) "
            "reasonable-relationship comparison can be made",
            "reasonable relationship with the height and massing of the main building",
        ),
        _e(
            "17.44.120(C)(2)",
            "placement_and_visual_clutter",
            T,
            "Location and elevation of the antenna and any support structures relative to the "
            "main building, for the (C)(2) visual-clutter review",
            "The placement of the antennae and any support structures shall be such that "
            "visual clutter shall be minimized",
        ),
        _e(
            "17.44.120(C)(3)",
            "collapsible_tower_considered",
            T,
            "Whether a collapsible or telescoping tower is proposed and, if so, its retracted "
            "height and location per (C)(3)",
            "The use of collapsible or telescoping towers shall be considered",
        ),
        _e(
            "17.44.120(D)",
            "adjacent_owner_notice_list",
            T,
            "Names and addresses of all adjacent property owners, so notice of the date and "
            "time of the Development Review Committee review hearing can be given under (D)",
            "Notice shall be given to adjacent property owners of date and time of the review "
            "hearing",
        ),
    ),
)

_RECYCLING = Section(
    section_id="17.44.140",
    title="Small recycling collection facilities",
    elements=(
        _e(
            "17.44.140",
            "area_within_500_square_feet",
            P,
            "the area the facility occupies, against the 500 sq ft ceiling",
            "Small recycling collection facilities which occupy an area of not more than 500 "
            "square feet are allowed as provided herein",
            bound=Bound(comparator=Comparator.AT_MOST, value=500, unit="square_feet"),
        ),
        _e(
            "17.44.140(A)",
            "in_conjunction_with_supermarket",
            T,
            "the supermarket the facility operates in conjunction with",
            "Permitted only in conjunction with a supermarket defined as full-time, "
            "self-service retail store",
        ),
        _e(
            "17.44.140(B)",
            "does_not_occupy_required_parking",
            P,
            "whether the facility occupies required parking spaces",
            "Shall not occupy required parking spaces",
        ),
        _e(
            "17.44.140(I)",
            "screened_from_right_of_way",
            P,
            "how the facility is screened from the public right-of-way",
            "Shall be screened from the public right-of-way",
        ),
    ),
)

_SATELLITE_ANTENNAE = Section(
    section_id="17.44.150",
    title="Satellite receiving antennae",
    elements=(
        _e(
            "17.44.150(A)",
            "screened_from_public_view",
            T,
            "how the antenna is screened from public view",
            "A satellite receiving antenna shall be screened from public view",
        ),
        _e(
            "17.44.150(B)",
            "diameter_not_over_three_feet",
            G,
            "the antenna's diameter, against the three-foot deeming threshold",
            "Any satellite receiving antennae which exceeds three feet in diameter or six "
            "feet in height shall, in residential zones, be deemed an accessory building",
            bound=Bound(comparator=Comparator.AT_MOST, value=3, unit="feet"),
        ),
        _e(
            "17.44.150(B)",
            "height_not_over_six_feet",
            G,
            "the antenna's height, against the six-foot deeming threshold",
            "exceeds three feet in diameter or six feet in height",
            bound=Bound(comparator=Comparator.AT_MOST, value=6, unit="feet"),
        ),
        _e(
            "17.44.150(B)",
            "precise_plan_of_design",
            T,
            "the precise plan of design required once the antenna is deemed an accessory building",
            "the applicant shall submit a precise plan of design",
            requires=(
                "17.44.150/diameter_not_over_three_feet",
                "17.44.150/height_not_over_six_feet",
            ),
        ),
    ),
)

_INDOOR_SWAP_MEET = Section(
    section_id="17.44.190",
    title="Indoor swap meets",
    elements=(
        _e(
            "17.44.190(A)",
            "permitted_zone",
            T,
            "the zoning designation of the property",
            "Indoor swap meets may be operated in the M and selected PD zones, if a "
            "conditional use permit is issued. Indoor swap meet uses are prohibited in all "
            "other zones.",
            zone_rule=ZoneRule(conditional=frozenset({"M", "PD"})),
        ),
    ),
)

_WIND_ENERGY = Section(
    section_id="17.44.215",
    title="Small wind energy systems",
    elements=(
        _e(
            "17.44.215(A)",
            "lot_one_acre_or_greater",
            T,
            "Parcel size in acres - 17.44.215(A) permits small wind energy systems only on "
            "lots one acre or greater, and the acreage also determines whether the 65-foot "
            "(1-5 acres) or 80-foot (over 5 acres) tower height cap in (B)(1) applies",
            "The development of small wind energy systems shall be permitted in any zone on "
            "lots one acre or greater in size",
            bound=Bound(comparator=Comparator.AT_LEAST, value=1, unit="acres"),
        ),
        _e(
            "17.44.215(A)",
            "turbine_certified",
            T,
            "the California Energy Commission approval or recognized national certification "
            "for the turbine",
            "must have a turbine approved by the California Energy Commission",
        ),
        _e(
            "17.44.215(B)(1)",
            "tower_height",
            P,
            "the tower height, against the 65-foot cap for parcels of one to five acres",
            "For parcels between one acre and five acres in size, tower height shall be no "
            "more than 65 feet",
            bound=Bound(comparator=Comparator.AT_MOST, value=65, unit="feet"),
        ),
        _e(
            "17.44.215(B)(1)",
            "manufacturer_height_evidence",
            T,
            "Evidence that the proposed tower height does not exceed the height recommended "
            "by the manufacturer or distributor of the system, required in the application "
            "by (B)(1)",
            "The application shall include evidence that the proposed height of the system "
            "does not exceed the manufacturer's recommended height for the system",
        ),
        _e(
            "17.44.215(B)(2)",
            "setback_at_least_system_height",
            P,
            "the setback from every property line, which must equal the height of the system",
            "the wind energy system shall be set back from any property line a distance equal "
            "to the height of the system",
            bound=Bound(
                comparator=Comparator.AT_LEAST,
                unit="feet",
                value_from="17.44.215/tower_height",
            ),
        ),
        _e(
            "17.44.215(B)(3)",
            "noise_level",
            P,
            "the noise level at the closest neighboring inhabited dwelling, against 60 decibels",
            "Noise levels for the system shall be no greater than either 60 decibels",
            bound=Bound(comparator=Comparator.AT_MOST, value=60, unit="decibels"),
        ),
        _e(
            "17.44.215(B)(4)",
            "engineering_analysis",
            T,
            "Standard drawings and an engineering analysis of the tower showing compliance "
            "with the UBC or California Building Standards Code, certified by a "
            "California-licensed mechanical, structural or civil engineer, required by (B)(4)",
            "The application shall include standard drawings and an engineering analysis of "
            "the tower",
        ),
        _e(
            "17.44.215(B)(5)",
            "safety_standards_demonstration",
            T,
            "the demonstration that the system meets the wind, seismic and soil requirements "
            "in (B)(5)",
            "The application must demonstrate that the system is designed to meet the most "
            "stringent wind requirements",
        ),
        _e(
            "17.44.215(B)(7)",
            "electrical_line_drawing",
            T,
            "the line drawing of the system's electrical components required by (B)(7)",
            "The application must include a line drawing of the electrical components of the "
            "system",
        ),
        _e(
            "17.44.215(B)(8)",
            "primarily_onsite_consumption",
            P,
            "whether the system is used primarily to reduce on-site consumption",
            "The system shall be used primarily to reduce onsite consumption of utility power",
        ),
        _e(
            "17.44.215(B)(9)",
            "not_on_historic_register",
            P,
            "whether the site is on the National Register of Historic Places or the "
            "California Register of Historical Resources",
            "shall not be permitted on any site that is listed on the National Register of "
            "Historic Places",
        ),
        _e(
            "17.44.215(B)(10)",
            "not_in_open_space_easement",
            P,
            "whether the parcel is part of an open space easement",
            "shall not be permitted on any parcel that is part of an Open Space Easement",
        ),
        _e(
            "17.44.215(B)(12)",
            "not_roof_mounted_on_residence",
            P,
            "whether the system is mounted on the roof of a residential structure",
            "A wind energy system may not be mounted on the roof of any residential structure",
        ),
    ),
)

#: Every section the rule layer can decide. A section absent from here is a
#: section the code cannot decide; :func:`decide` reports that honestly rather
#: than guessing.
SECTIONS: dict[str, Section] = {
    section.section_id: section
    for section in (
        _ADU,
        _BED_AND_BREAKFAST,
        _LARGE_DAY_CARE,
        _GAME_COURTS,
        _GASOLINE_TANKS,
        _HOME_OCCUPATION,
        _LATE_NIGHT,
        _CANNABIS,
        _TRANSMITTING_ANTENNAE,
        _RECYCLING,
        _SATELLITE_ANTENNAE,
        _INDOOR_SWAP_MEET,
        _PUBLIC_PROJECT_STORAGE,
        _WIND_ENERGY,
    )
}

#: Specific-controls-general. §17.44.030 expressly authorises the two things
#: §17.44.100 forbids generally, so for a bed-and-breakfast the general limits
#: do not apply. This is the harmonization the model failed on golden-008:
#: it co-retrieved §17.44.100, applied (F)/(G) to a B&B, and denied a case
#: whose only real defect was two unstated facts.
SUPPRESSIONS: tuple[Suppression, ...] = (
    Suppression(
        suppressed_provision="17.44.100(F)",
        controlling_provision="17.44.030(D)",
        when_section_present="17.44.030",
        reason=(
            "17.44.030(D) expressly permits an on-premise sign for a bed and breakfast "
            "home, so the general home-occupation sign bar in 17.44.100(F) does not apply"
        ),
    ),
    Suppression(
        suppressed_provision="17.44.100(G)",
        controlling_provision="17.44.030(B)",
        when_section_present="17.44.030",
        reason=(
            "17.44.030(B) expressly permits renting up to 50% of the bedrooms to a maximum "
            "of three, so the general one-room limit in 17.44.100(G) does not apply"
        ),
    ),
)

#: The §17.44.200 savings clause: when all four elements are established,
#: "the provisions of this Title 17 shall not be so construed as to limit, or
#: interfere with" the storage — so nothing else in Title 17 may be asked for.
SAVINGS_CLAUSE_ELEMENTS: tuple[str, ...] = tuple(
    element.key for element in _PUBLIC_PROJECT_STORAGE.elements
)


# --------------------------------------------------------------------------
# Evaluation.
# --------------------------------------------------------------------------


def _evaluate_bound(element: Element, fact: ProvisionFact, sheet: FactSheet) -> FactStatus | None:
    """Recompute the status from the stated value, or None to leave it alone."""
    bound = element.bound
    if bound is None:
        return None

    if bound.unit == "clock":
        minutes = parse_clock_minutes(fact.stated_value)
        if minutes is not None:
            in_window = bound.window_start_min <= minutes < bound.window_end_min
            return FactStatus.VIOLATED if in_window else FactStatus.SATISFIED
    else:
        quantity = parse_quantity(fact.stated_value, bound.unit)
        limit: float | None = bound.value
        if bound.value_from:
            source = sheet.get_by_element(bound.value_from)
            limit = parse_quantity(source.stated_value, bound.unit) if source else None
        if quantity is not None and limit is not None:
            ok = quantity <= limit if bound.comparator is Comparator.AT_MOST else quantity >= limit
            return FactStatus.SATISFIED if ok else FactStatus.VIOLATED

    # No value the code can compare. A relative or approximate statement does
    # not settle a numeric or clock-time threshold — §7.3 step 6's own rule.
    if fact.status in (FactStatus.SATISFIED, FactStatus.VIOLATED) and is_approximate(
        fact.stated_value
    ):
        return FactStatus.HEDGED
    return None


def _evaluate_zone(element: Element, fact: ProvisionFact) -> FactStatus | None:
    rule = element.zone_rule
    if rule is None:
        return None
    zone = parse_zone(fact.stated_value)
    if zone is None:
        return None
    if rule.forbidden:
        return FactStatus.VIOLATED if zone in rule.forbidden else FactStatus.SATISFIED
    if zone in rule.permitted or zone in rule.conditional:
        return FactStatus.SATISFIED
    return FactStatus.VIOLATED


def element_by_eid(eid: str) -> Element | None:
    """The registered element for a ``"<section>/<key>"`` id."""
    section_id, _, key = eid.partition("/")
    section = SECTIONS.get(section_id)
    if section is None:
        return None
    for element in section.elements:
        if element.key == key:
            return element
    return None


def _status_for(element: Element, sheet: FactSheet) -> tuple[FactStatus, ProvisionFact | None]:
    """The code's status for one element — its own reading beats the model's."""
    fact = sheet.get_by_element(element.eid)
    if fact is None:
        return FactStatus.ABSENT, None
    recomputed = _evaluate_zone(element, fact)
    if recomputed is None:
        recomputed = _evaluate_bound(element, fact, sheet)
    return (fact.status if recomputed is None else recomputed), fact


def _is_live(status: FactStatus) -> bool:
    """A dependency is live when it has fired or is unresolved."""
    return status is not FactStatus.SATISFIED


def _suppression_for(element: Element, sheet: FactSheet) -> Suppression | None:
    present = set(sheet.section_ids())
    for suppression in SUPPRESSIONS:
        if (
            suppression.suppressed_provision == element.provision
            and suppression.when_section_present in present
        ):
            return suppression
    return None


def evaluate(sheet: FactSheet) -> list[ElementVerdict]:
    """Every element of every engaged section, with its code-computed status.

    Two passes: statuses first (they depend only on facts and bounds), then
    applicability, which depends on other elements' statuses.
    """
    engaged = [sid for sid in sheet.section_ids() if sid in SECTIONS]
    statuses: dict[str, FactStatus] = {}
    facts: dict[str, ProvisionFact | None] = {}
    for section_id in engaged:
        for element in SECTIONS[section_id].elements:
            statuses[element.eid], facts[element.eid] = _status_for(element, sheet)

    savings_engaged = _SAVINGS_CLAUSE_SECTION in engaged and all(
        statuses.get(f"{_SAVINGS_CLAUSE_SECTION}/{key}") is FactStatus.SATISFIED
        for key in SAVINGS_CLAUSE_ELEMENTS
    )

    elements = [element for section_id in engaged for element in SECTIONS[section_id].elements]
    applicable = {element.eid: True for element in elements}
    reasons = {element.eid: "" for element in elements}
    for element in elements:
        if savings_engaged and element.section_id != _SAVINGS_CLAUSE_SECTION:
            applicable[element.eid] = False
            reasons[element.eid] = (
                "displaced by the 17.44.200 savings clause: Title 17 shall not be "
                "construed to limit or interfere with the temporary storage"
            )
        elif (suppression := _suppression_for(element, sheet)) is not None:
            applicable[element.eid] = False
            reasons[element.eid] = suppression.reason

    # `requires` chains, resolved to a fixpoint: a dependency that is itself
    # switched off cannot keep its dependants alive. §17.44.103 is why — when
    # the applicant states daytime-only hours, the 100-foot question goes quiet
    # AND so does the conditional use permit behind it.
    for _ in range(len(elements) + 1):
        changed = False
        for element in elements:
            if not applicable[element.eid] or not element.requires:
                continue
            if not any(
                applicable.get(dependency, False)
                and _is_live(statuses.get(dependency, FactStatus.ABSENT))
                for dependency in element.requires
            ):
                applicable[element.eid] = False
                reasons[element.eid] = (
                    f"not applicable: nothing in {', '.join(element.requires)} triggers it"
                )
                changed = True
        if not changed:
            break

    return [
        ElementVerdict(
            element=element,
            status=statuses[element.eid],
            applicable=applicable[element.eid],
            reason=reasons[element.eid],
            fact=facts[element.eid],
        )
        for element in elements
    ]


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def apply_ordered_rule(sheet: FactSheet, *, family: str = "") -> RuleOutcome:
    """The ordered decision rule, verbatim from the zoning agent's instruction.

    (1) an unambiguous violation of an applicable provision denies; (2) a
    decision-critical element that is absent or only hedged asks; (3) otherwise
    the stated facts satisfy every applicable requirement, and the application
    is approved as stated.
    """
    verdicts = evaluate(sheet)
    applicable = [v for v in verdicts if v.applicable]

    savings = [
        v
        for v in applicable
        if v.element.section_id == _SAVINGS_CLAUSE_SECTION and v.status is FactStatus.SATISFIED
    ]
    if len(savings) == len(SAVINGS_CLAUSE_ELEMENTS) and savings:
        return RuleOutcome(
            outcome=DeterminationOutcome.APPROVE,
            controlling_provisions=[_SAVINGS_CLAUSE_SECTION],
            controlling_element_ids=[v.element.eid for v in savings],
            rationale=(
                "Section 17.44.200 is a savings clause: the provisions of Title 17 shall not "
                "be construed to limit or interfere with the temporary occupation of land "
                "for storage in connection with a public project, provided the landowner "
                "consents and the Council first grants permission for a stated limited time. "
                "The application states all three conditions, so no other Title 17 "
                "requirement conditions this determination."
            ),
            verdicts=verdicts,
        )

    violations = [v for v in applicable if v.status is FactStatus.VIOLATED]
    # A fired TRIGGER records that a condition is present; it never denies on
    # its own. §17.44.103 late-night operation is the case in point: it makes
    # a conditional use permit necessary, it is not itself unlawful.
    denying = [v for v in violations if v.element.kind is not ElementKind.TRIGGER]
    if denying:
        return RuleOutcome(
            outcome=DeterminationOutcome.DENY,
            controlling_provisions=_dedupe([v.element.provision for v in denying]),
            controlling_element_ids=_dedupe([v.element.eid for v in denying]),
            rationale=(
                "The application states facts that violate "
                + "; ".join(f"{v.element.provision} ({v.element.summary})" for v in denying)
                + "."
            ),
            verdicts=verdicts,
        )

    # A trigger the application FIRED is resolved — the applicant told us the
    # condition holds. What is unresolved is whatever that trigger gates, and
    # those elements are live by the `requires` rule already.
    unresolved = [
        v
        for v in applicable
        if v.status is FactStatus.HEDGED
        or (v.status is FactStatus.ABSENT and v.element.kind is not ElementKind.PROHIBITION)
    ]
    if unresolved:
        return RuleOutcome(
            outcome=DeterminationOutcome.REQUEST_INFO,
            controlling_provisions=_dedupe([v.element.provision for v in unresolved]),
            controlling_element_ids=_dedupe([v.element.eid for v in unresolved]),
            rationale=(
                "The stated facts do not decide this application: "
                + "; ".join(f"{v.element.provision} - {v.element.summary}" for v in unresolved)
                + "."
            ),
            missing_elements=_dedupe([v.element.summary for v in unresolved]),
            verdicts=verdicts,
        )

    # Approve cites one satisfied provision per engaged section, so the
    # determination is grounded in every body of law that was applied.
    satisfied_by_section: list[ElementVerdict] = []
    for section_id in [sid for sid in sheet.section_ids() if sid in SECTIONS]:
        for verdict in applicable:
            if verdict.element.section_id == section_id and verdict.status is FactStatus.SATISFIED:
                satisfied_by_section.append(verdict)
                break
    return RuleOutcome(
        outcome=DeterminationOutcome.APPROVE,
        controlling_provisions=_dedupe([v.element.provision for v in satisfied_by_section]),
        controlling_element_ids=_dedupe([v.element.eid for v in satisfied_by_section]),
        rationale=(
            f"The stated facts satisfy every applicable requirement of "
            f"{', '.join(_dedupe([v.element.section_id for v in applicable]))}"
            + (f" for a {family} review" if family else "")
            + ". An application that meets the code as stated is approved as stated."
        ),
        verdicts=verdicts,
    )


RuleFn = Callable[[FactSheet], RuleOutcome]


def _rule_for(family: str) -> RuleFn:
    """Bind the ordered rule to one permit type.

    The dispatch that actually matters is by statute section, not by permit
    type: one permit type reaches many sections (``accessory_structure`` alone
    reaches eight of the fourteen in :data:`SECTIONS`) and one section serves
    many permit types. These per-type entries exist so a future permit type CAN
    diverge, and so the rationale names the review; today they differ only in
    that label. ADR-008 records the finding.
    """

    def rule(sheet: FactSheet) -> RuleOutcome:
        return apply_ordered_rule(sheet, family=family)

    return rule


#: Per-permit-type rule functions, keyed as in ``config/permit_types.yaml``.
RULES: dict[str, RuleFn] = {
    "garage_conversion": _rule_for("garage conversion"),
    "home_occupation": _rule_for("home occupation"),
    "accessory_structure": _rule_for("accessory structure"),
    "temporary_public_project_storage": _rule_for("temporary public project storage"),
}


def checklist_text(section_ids: list[str] | None = None) -> str:
    """The element checklist, rendered for the extraction agent's prompt.

    The registry is the single source of the element keys, so the extractor is
    told them rather than asked to invent them — a free-text key would not join
    back to a rule and the element would silently drop off the checklist.

    Deployed agent bundles cannot import workspace libraries (see
    ``caseflow_agent.schemas``), so the driver renders this locally and puts it
    in the request instead of the agent importing it.
    """
    wanted = section_ids or sorted(SECTIONS)
    lines: list[str] = []
    for section_id in wanted:
        section = SECTIONS.get(section_id)
        if section is None:
            continue
        lines.append(f"{section.section_id} {section.title}:")
        lines.extend(
            f"  - {element.key} [{element.provision}]: {element.summary}"
            for element in section.elements
        )
    return "\n".join(lines)


def rule_for_permit_type(permit_type: str) -> RuleFn:
    """The rule function for ``permit_type``, falling back to the ordered rule.

    An unconfigured permit type still gets a decision on the sections its facts
    engage; the verifier's step 4 is what escalates out-of-scope requests, and
    this layer must not quietly duplicate that judgement.
    """
    return RULES.get(permit_type, _rule_for(permit_type.replace("_", " ")))
