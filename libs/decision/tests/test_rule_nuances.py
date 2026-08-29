"""Each statute nuance the rules encode, pinned by a test that would notice.

The golden suite proves the layer gets 20/20; these prove it gets them right
for the stated reason. Every test here corresponds to a ruling in the B-006
study record, and most are written as a *flip*: the same facts with one thing
changed produce a different, also-correct outcome. A rule that merely memorised
the answer key would fail the flip.
"""

from pathlib import Path
from typing import ClassVar

import pytest
from civicnexus.contracts import DeterminationOutcome
from civicnexus.contracts.permit_types import PermitTypeConfig
from civicnexus.decision import (
    FactSheet,
    FactStatus,
    ProvisionFact,
    UndecidableError,
    apply_ordered_rule,
    decide,
    evaluate,
)
from civicnexus.decision.rules import (
    is_approximate,
    parse_clock_minutes,
    parse_quantity,
    parse_zone,
    rule_for_permit_type,
)

CORPUS = Path(__file__).resolve().parents[3] / "data" / "corpus"

S = FactStatus.SATISFIED
V = FactStatus.VIOLATED
H = FactStatus.HEDGED
A = FactStatus.ABSENT


def f(provision: str, element: str, status: FactStatus, value: str = "") -> ProvisionFact:
    return ProvisionFact(provision=provision, element=element, status=status, stated_value=value)


def _outcome(sheet: FactSheet) -> DeterminationOutcome:
    return apply_ordered_rule(sheet).outcome


class TestSpecificControlsGeneral:
    """§17.44.030 displaces §17.44.100(F)/(G) for a bed and breakfast.

    The mechanism that produced golden-008's deny: retrieval returned the
    general home-occupation section alongside the specific one, and the reader
    applied both. Two rented bedrooms violate §17.44.100(G); a wooden sign
    violates §17.44.100(F). Under §17.44.030 both are expressly authorised.
    """

    GENERAL: ClassVar[list[ProvisionFact]] = [
        f("17.44.100(F)", "no_nonresidential_signs", V, "a small wooden sign"),
        f("17.44.100(G)", "rooms_used", V, "two bedrooms"),
    ]
    SPECIFIC: ClassVar[list[ProvisionFact]] = [
        f("17.44.030(A)", "minimum_floor_area", S, "2,400 square feet"),
        f("17.44.030(B)", "rented_bedrooms", S, "two bedrooms"),
        f("17.44.030(C)", "owner_occupied", S, "the owners' principal residence"),
        f("17.44.030(D)", "sign_within_limits", S, "a small wooden sign"),
        f("17.44.030(H)", "required_parking", S, "two off-street spaces"),
    ]

    def test_general_limits_alone_would_deny(self) -> None:
        sheet = FactSheet(permit_type="home_occupation", facts=list(self.GENERAL))
        assert _outcome(sheet) is DeterminationOutcome.DENY

    def test_the_specific_section_displaces_them(self) -> None:
        sheet = FactSheet(permit_type="home_occupation", facts=[*self.SPECIFIC, *self.GENERAL])
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_the_displacement_is_recorded_with_its_reason(self) -> None:
        sheet = FactSheet(permit_type="home_occupation", facts=[*self.SPECIFIC, *self.GENERAL])
        suppressed = {v.element.provision: v.reason for v in evaluate(sheet) if not v.applicable}
        assert "17.44.030(D) expressly permits" in suppressed["17.44.100(F)"]
        assert "17.44.030(B) expressly permits" in suppressed["17.44.100(G)"]

    def test_only_the_expressly_authorised_general_limits_are_displaced(self) -> None:
        """§17.44.030 says nothing about employees, so §17.44.100(A) survives."""
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                *self.SPECIFIC,
                f("17.44.100(A)", "no_nonresident_employees", V, "a hired non-resident cook"),
            ],
        )
        assert _outcome(sheet) is DeterminationOutcome.DENY


class TestSavingsClause:
    """§17.44.200: consent plus Council permission for a stated time, and Title
    17 "shall not be so construed as to limit, or interfere with" the storage.
    """

    STRUCTURE_QUESTIONS: ClassVar[list[ProvisionFact]] = [
        f("17.44.005(B)(1)", "primary_dwelling_on_lot", A),
        f("17.44.005(E)(3)(a)", "side_and_rear_setback", A),
    ]
    CLAUSE: ClassVar[list[ProvisionFact]] = [
        f("17.44.200", "temporary_occupation_for_storage", S, "backhoes and pipe, temporarily"),
        f("17.44.200", "public_project_nexus", S, "City water main replacement"),
        f("17.44.200", "landowner_consent", S, "the owner-occupant signed the access letter"),
        f("17.44.200", "council_permission_for_stated_time", S, "120 days"),
    ]

    def test_all_four_elements_approve_and_silence_the_rest_of_title_17(self) -> None:
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[*self.CLAUSE, *self.STRUCTURE_QUESTIONS],
        )
        outcome = apply_ordered_rule(sheet)
        assert outcome.outcome is DeterminationOutcome.APPROVE
        assert outcome.controlling_provisions == ["17.44.200"]
        assert not outcome.missing_elements

    def test_without_the_clause_the_structure_questions_decide(self) -> None:
        sheet = FactSheet(permit_type="accessory_structure", facts=self.STRUCTURE_QUESTIONS)
        assert _outcome(sheet) is DeterminationOutcome.REQUEST_INFO

    @pytest.mark.parametrize(
        "dropped",
        ["landowner_consent", "council_permission_for_stated_time", "public_project_nexus"],
    )
    def test_an_unestablished_element_does_not_engage_the_clause(self, dropped: str) -> None:
        """Each condition is necessary — the clause is not a magic word."""
        facts = [
            fact if fact.element != dropped else f("17.44.200", dropped, A) for fact in self.CLAUSE
        ]
        sheet = FactSheet(
            permit_type="accessory_structure", facts=[*facts, *self.STRUCTURE_QUESTIONS]
        )
        outcome = apply_ordered_rule(sheet)
        assert outcome.outcome is DeterminationOutcome.REQUEST_INFO
        assert any("17.44.005" in provision for provision in outcome.controlling_provisions)


class TestHedgedNeverSatisfies:
    """ "An approximate or relative statement does not settle a numeric or
    clock-time threshold" — the §7.3 step-6 rule, enforced in code.

    The line is drawn at whether a NUMBER was stated, not at whether a hedging
    word appears: "about 3 feet" quantifies and is decided on its quantity;
    "well before sunrise" does not quantify at all.
    """

    def test_a_relative_time_does_not_settle_the_clock_threshold(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.103(B)", "no_late_night_operation", S, "well before sunrise")],
        )
        verdict = next(v for v in evaluate(sheet) if v.element.key == "no_late_night_operation")
        assert verdict.status is FactStatus.HEDGED
        assert _outcome(sheet) is DeterminationOutcome.REQUEST_INFO

    def test_an_approximate_distance_does_not_settle_a_footage_threshold(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.060(C)", "no_other_day_care_facility_nearby", V, "another day care"),
                f(
                    "17.44.060(C)",
                    "not_within_1000ft_of_other_large_facility",
                    S,
                    "two houses down the block",
                ),
            ],
        )
        verdict = next(
            v
            for v in evaluate(sheet)
            if v.element.key == "not_within_1000ft_of_other_large_facility"
        )
        assert verdict.status is FactStatus.HEDGED

    def test_a_quantified_value_is_decided_on_its_quantity_despite_the_hedge(self) -> None:
        """golden-015's "about 3 feet" is 3 feet, and 3 is under 6."""
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[
                f("17.44.150(A)", "screened_from_public_view", S, "behind a solid block wall"),
                f("17.44.150(B)", "diameter_not_over_three_feet", S, "24 inches"),
                f("17.44.150(B)", "height_not_over_six_feet", S, "about 3 feet"),
            ],
        )
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_an_undecided_room_count_asks_rather_than_denies(self) -> None:
        """golden-004: the over-decide the ordered rule's step 1 forbids."""
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(G)", "rooms_used", H, "a bedroom and maybe part of the garage")],
        )
        assert _outcome(sheet) is DeterminationOutcome.REQUEST_INFO


class TestLateNightApplicability:
    """§17.44.103(C) needs BOTH midnight-6am operation AND 100-foot proximity."""

    def test_stated_daytime_hours_switch_the_whole_section_off(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.100(G)", "rooms_used", S, "one room"),
                f("17.44.103(B)", "no_late_night_operation", S, "8:00 a.m."),
            ],
        )
        off = {v.element.key: v.applicable for v in evaluate(sheet)}
        assert off["not_within_100ft_of_residential_zone"] is False
        assert off["conditional_use_permit"] is False
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_late_night_beyond_100_feet_requires_nothing(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.100(G)", "rooms_used", S, "one room"),
                f("17.44.103(B)", "no_late_night_operation", S, "5:00 a.m."),
                f("17.44.103(C)", "not_within_100ft_of_residential_zone", S, "200 feet"),
            ],
        )
        verdicts = {v.element.key: v for v in evaluate(sheet)}
        assert verdicts["no_late_night_operation"].status is FactStatus.VIOLATED
        assert verdicts["conditional_use_permit"].applicable is False
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_late_night_within_100_feet_asks_for_the_permit(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.103(B)", "no_late_night_operation", S, "5:00 a.m."),
                f("17.44.103(C)", "not_within_100ft_of_residential_zone", S, "50 feet"),
            ],
        )
        outcome = apply_ordered_rule(sheet)
        assert outcome.outcome is DeterminationOutcome.REQUEST_INFO
        assert any("conditional use permit" in m for m in outcome.missing_elements)

    def test_a_fired_trigger_is_never_by_itself_a_denial(self) -> None:
        """Operating late-night is regulated, not unlawful."""
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.103(B)", "no_late_night_operation", S, "2:00 a.m."),
                f("17.44.103(C)", "not_within_100ft_of_residential_zone", S, "500 feet"),
            ],
        )
        assert _outcome(sheet) is not DeterminationOutcome.DENY


class TestCodeOverridesTheModel:
    """Where the code can compute the answer, the model's status does not vote."""

    def test_a_stated_zone_is_classified_by_code_not_by_the_reader(self) -> None:
        """Pro asked whether golden-009 was residential while "RL" was on the page."""
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[
                f("17.44.080", "no_above_ground_tank_outside_buildings", V, "a 300-gallon tank"),
                # The extractor got this wrong on purpose; the code does not care.
                f("17.44.080", "tank_not_in_residential_zone", S, "RL"),
            ],
        )
        assert _outcome(sheet) is DeterminationOutcome.DENY

    def test_no_tank_means_the_zone_question_never_arises(self) -> None:
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[
                f("17.44.080", "no_above_ground_tank_outside_buildings", S, "no tank proposed"),
                f("17.44.080", "tank_not_in_residential_zone", S, "RL"),
            ],
        )
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_a_count_over_the_cap_is_a_violation_whatever_the_reader_said(self) -> None:
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[f("17.44.104(F)(3)", "plant_count", S, "twelve plants")],
        )
        assert _outcome(sheet) is DeterminationOutcome.DENY

    def test_a_count_under_the_cap_is_not_a_violation_whatever_the_reader_said(self) -> None:
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[f("17.44.104(F)(3)", "plant_count", V, "four plants")],
        )
        assert _outcome(sheet) is not DeterminationOutcome.DENY

    def test_a_dynamic_bound_reads_its_limit_from_another_element(self) -> None:
        """§17.44.215(B)(2): the setback must equal the height of the system."""
        short = FactSheet(
            permit_type="accessory_structure",
            facts=[
                f("17.44.215(B)(1)", "tower_height", S, "55 feet"),
                f("17.44.215(B)(2)", "setback_at_least_system_height", S, "30 feet"),
            ],
        )
        assert _outcome(short) is DeterminationOutcome.DENY


class TestOverAskDiscipline:
    """Silence about a prohibition is not a reason to write to the applicant."""

    def test_silence_on_prohibitions_still_approves(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(G)", "rooms_used", S, "one room")],
        )
        assert _outcome(sheet) is DeterminationOutcome.APPROVE

    def test_silence_on_an_eligibility_threshold_asks(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[
                f("17.44.030(A)", "minimum_floor_area", A),
                f("17.44.030(C)", "owner_occupied", S, "principal residence"),
            ],
        )
        outcome = apply_ordered_rule(sheet)
        assert outcome.outcome is DeterminationOutcome.REQUEST_INFO
        assert any("2,000 sq ft" in m for m in outcome.missing_elements)

    def test_a_violation_outranks_an_unanswered_question(self) -> None:
        """Ordered rule step 1 precedes step 2, so a deny is never softened."""
        sheet = FactSheet(
            permit_type="accessory_structure",
            facts=[
                f("17.44.104(F)(3)", "plant_count", V, "twelve plants"),
                f("17.44.104(F)(9)", "fire_extinguisher_in_residence", A),
            ],
        )
        assert _outcome(sheet) is DeterminationOutcome.DENY


class TestParsers:
    @pytest.mark.parametrize(
        ("value", "unit", "expected"),
        [
            ("640 square feet", "square_feet", 640.0),
            ("roughly 120 square feet", "square_feet", 120.0),
            ("24 inches", "feet", 2.0),
            ("about 3 feet", "feet", 3.0),
            ("a 55-foot monopole tower", "feet", 55.0),
            ("twelve plants", "plants", 12.0),
            ("two bedrooms", "rooms", 2.0),
            ("about 45 decibels", "decibels", 45.0),
            # Ambiguous or absent: the code declines rather than guesses.
            ("four bedrooms of which we rent two bedrooms", "bedrooms", None),
            ("two houses down the block", "feet", None),
            ("well before sunrise", "feet", None),
            ("640 square feet", "acres", None),
        ],
    )
    def test_parse_quantity(self, value: str, unit: str, expected: float | None) -> None:
        assert parse_quantity(value, unit) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("5:00 a.m.", 300),
            ("8:00 a.m.", 480),
            ("11 p.m.", 1380),
            ("midnight", 0),
            ("well before sunrise", None),
            ("between 5 a.m. and 9 a.m.", None),
        ],
    )
    def test_parse_clock_minutes(self, value: str, expected: int | None) -> None:
        assert parse_clock_minutes(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("RL", "RL"),
            ("R-1", "R1"),
            ("C-R/S", "CRS"),
            ("zoned M", "M"),
            ("The zoning map shows our lot as RL", "RL"),
            ("", None),
            # Two candidates: ambiguous, so the code declines to classify.
            ("RL or RM", None),
        ],
    )
    def test_parse_zone(self, value: str, expected: str | None) -> None:
        assert parse_zone(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("about 3 feet", True),
            ("well before sunrise", True),
            ("maybe", True),
            ("two houses down the block", True),
            ("55 feet", False),
            ("RL", False),
            ("no street yard on the side", False),
        ],
    )
    def test_is_approximate(self, value: str, expected: bool) -> None:
        assert is_approximate(value) is expected


class TestDecideSurface:
    def test_an_unknown_section_is_reported_not_guessed(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.999(A)", "invented", V, "something")],
        )
        with pytest.raises(UndecidableError, match="no rules"):
            decide(sheet, None, corpus_dir=CORPUS)

    def test_outcome_legality_is_reported_never_rewritten(self) -> None:
        """Steering an outcome to fit config is prime-directive-9 territory."""
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(E)", "no_outside_storage", V, "pallets in the side yard")],
        )
        cfg = PermitTypeConfig(
            required_capabilities=["zoning"],
            allowed_outcomes=[DeterminationOutcome.APPROVE],
            sla_days=10,
        )
        result = decide(sheet, cfg, corpus_dir=CORPUS)
        assert result.outcome is DeterminationOutcome.DENY
        assert result.outcome_allowed is False

    def test_an_unconfigured_permit_type_still_gets_the_ordered_rule(self) -> None:
        sheet = FactSheet(
            permit_type="tree_removal",
            facts=[f("17.44.100(E)", "no_outside_storage", V, "pallets in the side yard")],
        )
        assert rule_for_permit_type("tree_removal")(sheet).outcome is DeterminationOutcome.DENY

    def test_citations_carry_the_corpus_span_not_the_rule_table_text(self) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(E)", "no_outside_storage", V, "pallets in the side yard")],
        )
        result = decide(sheet, None, corpus_dir=CORPUS)
        section = (CORPUS / "17.44.100.txt").read_text(encoding="utf-8")
        assert result.citations[0].quote in section

    def test_a_corpus_that_no_longer_says_it_fails_loudly(self, tmp_path: Path) -> None:
        (tmp_path / "17.44.100.txt").write_text("nothing of the kind", encoding="utf-8")
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(E)", "no_outside_storage", V, "pallets in the side yard")],
        )
        with pytest.raises(UndecidableError, match="diverged"):
            decide(sheet, None, corpus_dir=tmp_path)

    def test_a_missing_corpus_section_fails_loudly(self, tmp_path: Path) -> None:
        sheet = FactSheet(
            permit_type="home_occupation",
            facts=[f("17.44.100(E)", "no_outside_storage", V, "pallets in the side yard")],
        )
        with pytest.raises(UndecidableError, match="not in the corpus"):
            decide(sheet, None, corpus_dir=tmp_path)
