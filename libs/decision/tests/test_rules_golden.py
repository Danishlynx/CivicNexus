"""The rule layer against all 20 PermitBench golden cases, offline.

Each case supplies the fact sheet a correct extraction would produce from its
fixture text — nothing more. Everything downstream is code, so this file
answers one question: *given the facts, do the written rules reach the right
outcome every time?* If they do, the residual error in the live system is
extraction, and that is a different, narrower problem.

Three guards keep this from being a test that grades its own homework:

* Expectations are loaded from ``evals/permitbench/cases/*.yaml`` — the frozen
  dataset — not retyped here. The test cannot drift from the eval.
* Every ``quote`` is asserted to be a verbatim span of that case's fixture
  document, so a fact sheet cannot smuggle in a fact the applicant never wrote.
* Every ``element`` key is asserted to exist in the rule registry, so a typo
  cannot silently make an element vanish from the checklist.

The dependency on ``evals`` is deliberate and one-way (root ``conftest.py`` puts
the repo root on ``sys.path``); the shipped package imports nothing from it.
"""

from pathlib import Path

import pytest
from civicnexus.contracts import DeterminationOutcome
from civicnexus.decision import FactSheet, FactStatus, ProvisionFact, decide
from civicnexus.decision.decide import verbatim_span
from civicnexus.decision.rules import SECTIONS, element_by_eid

from evals.permitbench.schema import CORPUS_DIR, REPO_ROOT, EvalCase, load_all

S = FactStatus.SATISFIED
V = FactStatus.VIOLATED
H = FactStatus.HEDGED
A = FactStatus.ABSENT


def f(
    provision: str,
    element: str,
    status: FactStatus,
    stated_value: str = "",
    quote: str = "",
) -> ProvisionFact:
    return ProvisionFact(
        provision=provision,
        element=element,
        status=status,
        stated_value=stated_value,
        quote=quote,
    )


# --------------------------------------------------------------------------
# The fact sheets. One per golden case, read off the fixture documents.
# --------------------------------------------------------------------------

_HOME_OCC = "17.44.100"


def _sheet_001() -> FactSheet:
    return FactSheet(
        permit_type="garage_conversion",
        facts=[
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                S,
                "no employees",
                "I would run entirely by myself - no employees",
            ),
            f(
                f"{_HOME_OCC}(B)",
                "normal_materials_and_equipment",
                S,
                "a normal kitchen setup",
                "Just a normal kitchen setup inside using regular household power and water",
            ),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "no customers coming to the house",
                "no customers coming to the house",
            ),
            f(
                f"{_HOME_OCC}(D)",
                "no_commercial_delivery_vehicles",
                S,
                "delivery in my own car",
                "deliver to the farmers market in my own car",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                S,
                "nothing stored outside",
                "nothing stored outside",
            ),
            f(f"{_HOME_OCC}(F)", "no_nonresidential_signs", S, "no sign", "No sign on the house"),
            f(
                f"{_HOME_OCC}(G)",
                "rooms_used",
                S,
                "one room",
                "convert one room of my attached garage",
            ),
            f(
                f"{_HOME_OCC}(H)",
                "appearance_stays_residential",
                S,
                "no exterior change",
                "I'm not changing the outside of the garage at all - same door, same paint",
            ),
            f(
                f"{_HOME_OCC}(I)",
                "normal_utility_use",
                S,
                "regular household power and water",
                "using regular household power and water",
            ),
        ],
    )


def _sheet_002() -> FactSheet:
    return FactSheet(
        permit_type="garage_conversion",
        facts=[
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                V,
                "a sister who lives across town, not with us",
                "My sister will work with me every day - she lives across town, not with us",
            ),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "no customers at the house",
                "no customers at the house",
            ),
            f(
                f"{_HOME_OCC}(D)",
                "no_commercial_delivery_vehicles",
                S,
                "deliveries in my own car",
                "deliveries in my own car",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                S,
                "nothing stored outside",
                "nothing stored outside",
            ),
            f(f"{_HOME_OCC}(F)", "no_nonresidential_signs", S, "no signage", "no signage"),
            f(f"{_HOME_OCC}(G)", "rooms_used", S, "one room", "one room only"),
            f(
                f"{_HOME_OCC}(H)",
                "appearance_stays_residential",
                S,
                "no change to the garage",
                "no changes to how the garage looks",
            ),
        ],
    )


def _sheet_003() -> FactSheet:
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                S,
                "just me, no staff",
                "just me, no staff",
            ),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "clients by scheduled appointment only",
                "clients only by scheduled appointment",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                S,
                "no outside storage",
                "no outside storage",
            ),
            f(
                f"{_HOME_OCC}(F)",
                "no_nonresidential_signs",
                V,
                "a lighted 4-foot by 6-foot business sign, lit in the evenings",
                "I want to mount a lighted 4-foot by 6-foot sign on the front of the garage "
                "saying the business name, lit in the evenings",
            ),
            f(f"{_HOME_OCC}(G)", "rooms_used", S, "one room", "one room used"),
            f(
                f"{_HOME_OCC}(H)",
                "appearance_stays_residential",
                S,
                "otherwise residential",
                "Everything else stays residential",
            ),
            f(f"{_HOME_OCC}(I)", "normal_utility_use", S, "normal utilities", "normal utilities"),
        ],
    )


def _sheet_004() -> FactSheet:
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(f"{_HOME_OCC}(A)", "no_nonresident_employees", S, "solo operation", "Solo operation"),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "no customers visiting",
                "no customers visiting",
            ),
            f(
                f"{_HOME_OCC}(D)",
                "no_commercial_delivery_vehicles",
                S,
                "regular mail pickup",
                "shipping through regular mail pickup",
            ),
            f(f"{_HOME_OCC}(F)", "no_nonresidential_signs", S, "no signs", "no signs"),
            # The hedge the whole case turns on. No room count is stated, and
            # "maybe"/"haven't decided" is not a stated fact.
            f(
                f"{_HOME_OCC}(G)",
                "rooms_used",
                H,
                "the spare bedroom and maybe part of the garage, not yet decided",
                "I plan to use the spare bedroom, and maybe also part of the garage for the "
                "inventory racks, I haven't decided how much space I'll need yet",
            ),
        ],
    )


def _sheet_005() -> FactSheet:
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(f"{_HOME_OCC}(A)", "no_nonresident_employees", S, "no employees", "No employees"),
            f(
                f"{_HOME_OCC}(B)",
                "normal_materials_and_equipment",
                S,
                "standard power tools on household current",
                "standard power tools on household current",
            ),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "no customer visits",
                "no customer visits",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                V,
                "lumber stock on a covered rack outside along the side yard fence",
                "I'd keep my lumber stock on a covered rack along the side yard fence outside",
            ),
            f(f"{_HOME_OCC}(F)", "no_nonresidential_signs", S, "no signage", "no signage"),
            f(f"{_HOME_OCC}(G)", "rooms_used", S, "one room", "in one room of my garage"),
            f(f"{_HOME_OCC}(I)", "normal_utility_use", S, "household current", "household current"),
        ],
    )


def _sheet_006() -> FactSheet:
    return FactSheet(
        permit_type="garage_conversion",
        facts=[
            f(
                "17.44.005(B)(1)",
                "primary_dwelling_on_lot",
                S,
                "an existing house on the lot",
                "I own the house at 121 Colon Burg (synthetic)",
            ),
            f(
                "17.44.005(D)(1)(a)2.c.",
                "conversion_expansion_square_feet",
                V,
                "about another 400 square feet",
                "We would also build an addition off the back of it adding about another 400 "
                "square feet",
            ),
            f(
                "17.44.005(E)(3)(a)",
                "side_and_rear_setback",
                V,
                "about 2 feet",
                "The new addition would sit about 2 feet from the side property line",
            ),
        ],
    )


def _sheet_007() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                "17.44.005(B)(1)",
                "primary_dwelling_on_lot",
                S,
                "an existing single-family house",
                "behind our single-family house",
            ),
            f(
                "17.44.005(D)(1)(b)1.b.",
                "new_detached_adu_square_feet",
                S,
                "640 square feet",
                "Plans call for 640 square feet",
            ),
            f(
                "17.44.005(D)(1)(b)3.",
                "detached_adu_height",
                S,
                "15 feet",
                "15 feet to the top of the roof",
            ),
            f(
                "17.44.005(E)(3)(a)",
                "side_and_rear_setback",
                S,
                "5 feet",
                "sitting 5 feet off the side property line and 5 feet off the rear property line",
            ),
            f(
                "17.44.005(G)(1)",
                "rental_term",
                S,
                "regular year-long leases",
                "We would rent it on regular year-long leases to a local teacher, nothing "
                "short-term or vacation-type",
            ),
        ],
    )


def _sheet_008() -> FactSheet:
    """Bed and breakfast — including the §17.44.100 co-retrieval that sank it live.

    The 2026-08-28 Flash run cited ``['17.44.100', '17.44.030']`` and denied.
    Those general facts are reported here exactly as the model reported them,
    so the rules have to perform the harmonization rather than be spared it.
    """
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f("17.44.030(A)", "minimum_floor_area", A),
            f(
                "17.44.030(B)",
                "rented_bedrooms",
                S,
                "two bedrooms",
                "we would rent out only two of them upstairs",
            ),
            f(
                "17.44.030(C)",
                "owner_occupied",
                S,
                "the owners' only residence, lived in full time",
                "in our own home, which we live in full time as our only residence",
            ),
            f(
                "17.44.030(D)",
                "sign_within_limits",
                S,
                "a small wooden sign by the front porch",
                "We would like a small wooden sign by the front porch",
            ),
            f(
                "17.44.030(E)",
                "no_guest_room_cooking",
                S,
                "no kitchenettes or hot plates",
                "no kitchenettes or hot plates in the guest rooms",
            ),
            f(
                "17.44.030(F)",
                "meals_limited",
                S,
                "breakfast only",
                "Breakfast only, served in the dining room",
            ),
            f(
                "17.44.030(G)",
                "occupancy_length",
                S,
                "a couple of nights, never more than a week",
                "Guests would stay a couple of nights at a time, never more than a week",
            ),
            f("17.44.030(H)", "required_parking", A),
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                S,
                "the owners themselves",
                "My husband and I want to start taking in overnight guests",
            ),
            f(
                f"{_HOME_OCC}(F)",
                "no_nonresidential_signs",
                V,
                "a small wooden sign by the front porch",
                "We would like a small wooden sign by the front porch",
            ),
            f(
                f"{_HOME_OCC}(G)",
                "rooms_used",
                V,
                "two bedrooms",
                "we would rent out only two of them upstairs",
            ),
        ],
    )


def _sheet_009() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                "17.44.080",
                "no_above_ground_tank_outside_buildings",
                V,
                "a 300-gallon above-ground gasoline storage tank, outside",
                "I'd like to install a 300-gallon above-ground gasoline storage tank on a new "
                "concrete pad in my back yard, outside",
            ),
            # The zone is a stated token; classifying RL as residential is the
            # code's job. Pro asked for this fact on 2026-08-28 while it was on
            # the page.
            f(
                "17.44.080",
                "tank_not_in_residential_zone",
                V,
                "RL",
                "the zoning map shows it as RL",
            ),
        ],
    )


def _sheet_010() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f("17.44.070", "permitted_zone", S, "RL", "The zoning map shows our lot as RL"),
            f(
                "17.44.070(A)",
                "side_yard_setback_interior_lot",
                S,
                "8 feet",
                "The slab would sit 8 feet in from the north side property line",
            ),
            f("17.44.070(A)", "alley_side_setback", S, "4 feet", "4 feet back from the alley"),
            f(
                "17.44.070(A)",
                "street_yard_setback",
                S,
                "no street yard on this interior lot",
                "we're not on a corner, so there's no street yard on the side",
            ),
            f("17.44.070(B)", "lighting", S, "no lighting", "no lighting at all"),
            f("17.44.070(C)", "fencing_and_landscaping", S, "no new fencing", "No new fencing"),
        ],
    )


def _sheet_011() -> FactSheet:
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(
                "17.44.060(B)",
                "hours_of_operation",
                S,
                "7:00 a.m. to 6:00 p.m.",
                "Hours would be 7:00 a.m. to 6:00 p.m., Monday through Friday",
            ),
            f(
                "17.44.060(C)",
                "no_other_day_care_facility_nearby",
                V,
                "another day care two houses down the block",
                "there's another day care family two houses down the block",
            ),
            f("17.44.060(C)", "other_facility_is_not_a_large_family_day_care", A),
            f(
                "17.44.060(C)",
                "not_within_1000ft_of_other_large_facility",
                H,
                "two houses down the block",
                "two houses down the block",
            ),
            f("17.44.060(C)", "adverse_impact_showing", A),
        ],
    )


_CANN = "17.44.104"


def _sheet_012() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                f"{_CANN}(F)(1)",
                "cultivator_over_21_and_secured_from_minors",
                S,
                "both spouses over 21, the only adults in the house",
                "My spouse and I are both over 21 and we are the only adults in the house",
            ),
            f(
                f"{_CANN}(F)(2)",
                "fully_enclosed_and_secure_structure",
                S,
                "fully enclosed, one lockable door, no windows",
                "The shed would be fully enclosed with solid walls and a roof, one lockable "
                "door, no windows",
            ),
            f(
                f"{_CANN}(F)(3)",
                "plant_count",
                V,
                "twelve plants",
                "we are planning on twelve plants total, six each",
            ),
            f(
                f"{_CANN}(F)(4)",
                "no_co2_or_ozone_generators",
                S,
                "none",
                "no CO2 or ozone generators",
            ),
            f(
                f"{_CANN}(F)(5)",
                "no_compressed_gases",
                S,
                "none",
                "no butane or compressed gas of any kind",
            ),
            f(
                f"{_CANN}(F)(6)",
                "not_visible_from_public_right_of_way",
                S,
                "not visible",
                "Nothing will be visible from the street",
            ),
            f(
                f"{_CANN}(F)(11)",
                "electrical_directly_connected",
                S,
                "plugged into a wall outlet",
                "Grow lights plug into a wall outlet",
            ),
            f(f"{_CANN}(F)(7)", "dwelling_remains_a_residence", A),
            f(f"{_CANN}(F)(8)", "no_public_nuisance", A),
            f(f"{_CANN}(F)(9)", "fire_extinguisher_in_residence", A),
            f(f"{_CANN}(F)(10)", "does_not_displace_parking", A),
        ],
    )


def _sheet_013() -> FactSheet:
    """Four plants — every one of the eleven (F) standards is on the page.

    Both Flash and Pro asked for the applicant's age, the absence of minors and
    the fire extinguisher; all three are stated. This is the over-ask class in
    its purest form.
    """
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                f"{_CANN}(F)(1)",
                "cultivator_over_21_and_secured_from_minors",
                S,
                "both over 21, no minors resident, keys held only by the two of them",
                "only my wife and I have keys and we are both over 21, and no minors live at "
                "the house",
            ),
            f(
                f"{_CANN}(F)(2)",
                "fully_enclosed_and_secure_structure",
                S,
                "solid walls to the roof, no windows, one lockable door",
                "Solid walls up to the roof, no windows, one lockable door",
            ),
            f(
                f"{_CANN}(F)(3)",
                "plant_count",
                S,
                "four plants",
                "Inside we would grow four cannabis plants for our own use",
            ),
            f(
                f"{_CANN}(F)(4)",
                "no_co2_or_ozone_generators",
                S,
                "none",
                "No CO2 or ozone generators",
            ),
            f(f"{_CANN}(F)(5)", "no_compressed_gases", S, "none", "no butane or compressed gas"),
            f(
                f"{_CANN}(F)(6)",
                "not_visible_from_public_right_of_way",
                S,
                "not visible from the street or sidewalk",
                "it is not visible from the street or sidewalk",
            ),
            f(
                f"{_CANN}(F)(7)",
                "dwelling_remains_a_residence",
                S,
                "full-time residence",
                "The house remains our full-time residence",
            ),
            f(
                f"{_CANN}(F)(8)",
                "no_public_nuisance",
                S,
                "carbon filter, no odor at the line",
                "Carbon filter on the exhaust, so no odor at the property line",
            ),
            f(
                f"{_CANN}(F)(9)",
                "fire_extinguisher_in_residence",
                S,
                "kept in the kitchen",
                "Fire extinguisher stays in the kitchen",
            ),
            f(
                f"{_CANN}(F)(10)",
                "does_not_displace_parking",
                S,
                "sited on lawn, not the driveway",
                "the shed sits on lawn, not on the driveway parking",
            ),
            f(
                f"{_CANN}(F)(11)",
                "electrical_directly_connected",
                S,
                "plugged directly into a wall outlet",
                "Grow lights plug directly into a wall outlet",
            ),
        ],
    )


def _sheet_014() -> FactSheet:
    """Home bakery, pre-dawn hours. Fixture as repaired 2026-08-29 (B-006 add. 3).

    Every §17.44.100 element is satisfied, so the case turns entirely on
    §17.44.103 — which is what the expectation always said and what both models
    missed by citing §17.44.100 and denying.
    """
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                S,
                "the applicant and a resident daughter",
                "No employees, it is just me and my daughter who lives here",
            ),
            f(
                f"{_HOME_OCC}(C)",
                "no_excess_traffic",
                S,
                "customer pickups twice a week",
                "customers pick up maybe twice a week",
            ),
            f(
                f"{_HOME_OCC}(D)",
                "no_commercial_delivery_vehicles",
                S,
                "the applicant's own car, no delivery trucks",
                "I drive my own car to the markets, no delivery trucks",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                S,
                "no outside storage",
                "no outside storage",
            ),
            f(f"{_HOME_OCC}(F)", "no_nonresidential_signs", S, "no sign", "No sign out front"),
            f(
                f"{_HOME_OCC}(G)",
                "rooms_used",
                S,
                "one room",
                "All of the business baking happens in one room",
            ),
            # Relative, not a clock time: it cannot settle the midnight-6am line.
            f(
                "17.44.103(B)",
                "no_late_night_operation",
                H,
                "well before sunrise",
                "on market weekends I am up and working well before sunrise",
            ),
            f("17.44.103(C)", "not_within_100ft_of_residential_zone", A),
            f("17.44.103(C)", "conditional_use_permit", A),
        ],
    )


def _sheet_015() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                "17.44.150(A)",
                "screened_from_public_view",
                S,
                "not visible from the street, sidewalk or alley",
                "the dish can't be seen from the street, the sidewalk, or the alley",
            ),
            f(
                "17.44.150(B)",
                "diameter_not_over_three_feet",
                S,
                "24 inches",
                "It's a small one, 24 inches across",
            ),
            f(
                "17.44.150(B)",
                "height_not_over_six_feet",
                S,
                "about 3 feet",
                "Top of the dish sits about 3 feet off the ground",
            ),
        ],
    )


def _sheet_016() -> FactSheet:
    return FactSheet(
        permit_type="home_occupation",
        facts=[
            f(
                "17.44.140",
                "area_within_500_square_feet",
                S,
                "roughly 120 square feet",
                "roughly 120 square feet total",
            ),
            f(
                "17.44.140(A)",
                "in_conjunction_with_supermarket",
                V,
                "no store or market on the lot",
                "It's a single-family house, there's no store or market on the lot",
            ),
            f(
                f"{_HOME_OCC}(A)",
                "no_nonresident_employees",
                V,
                "one part-time helper, a neighbour rather than family",
                "I'd also hire one part-time helper for weekends - he's a neighbor, not family",
            ),
            f(
                f"{_HOME_OCC}(D)",
                "no_commercial_delivery_vehicles",
                V,
                "a hauler's flatbed truck twice a week",
                "I have a hauler lined up who'd bring his flatbed truck by twice a week",
            ),
            f(
                f"{_HOME_OCC}(E)",
                "no_outside_storage",
                V,
                "bins outside around the clock",
                "The bins would stay outside around the clock",
            ),
            f(
                f"{_HOME_OCC}(F)",
                "no_nonresidential_signs",
                V,
                "a sandwich board by the curb",
                "No signage other than a small sandwich board by the curb",
            ),
        ],
    )


def _sheet_017() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f("17.44.120(C)(1)", "antenna_total_height", A),
            f("17.44.120(C)(1)", "main_building_height_and_massing", A),
            f("17.44.120(C)(2)", "placement_and_visual_clutter", A),
            f("17.44.120(C)(3)", "collapsible_tower_considered", A),
            f("17.44.120(D)", "adjacent_owner_notice_list", A),
        ],
    )


def _sheet_018() -> FactSheet:
    return FactSheet(
        permit_type="garage_conversion",
        facts=[
            f(
                "17.44.190(A)",
                "permitted_zone",
                V,
                "R-1",
                "we own the single-family home at 3374 Theodore Summit (synthetic), zoned R-1",
            ),
        ],
    )


_WIND = "17.44.215"


def _sheet_019() -> FactSheet:
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(f"{_WIND}(A)", "lot_one_acre_or_greater", A),
            f(
                f"{_WIND}(A)",
                "turbine_certified",
                S,
                "CEC-certified",
                "a ground-mounted, CEC-certified turbine",
            ),
            f(f"{_WIND}(B)(1)", "tower_height", S, "55 feet", "a 55-foot monopole tower"),
            f(f"{_WIND}(B)(1)", "manufacturer_height_evidence", A),
            f(
                f"{_WIND}(B)(2)",
                "setback_at_least_system_height",
                S,
                "90 feet",
                "at least 90 feet from every property line",
            ),
            f(
                f"{_WIND}(B)(3)",
                "noise_level",
                S,
                "about 45 decibels",
                "the manufacturer's spec sheet lists about 45 decibels at 100 feet",
            ),
            f(f"{_WIND}(B)(4)", "engineering_analysis", A),
            f(f"{_WIND}(B)(5)", "safety_standards_demonstration", A),
            f(f"{_WIND}(B)(7)", "electrical_line_drawing", A),
            f(
                f"{_WIND}(B)(8)",
                "primarily_onsite_consumption",
                S,
                "all power used on site",
                "we'd use all the power ourselves rather than selling it back",
            ),
            f(
                f"{_WIND}(B)(9)",
                "not_on_historic_register",
                S,
                "not on any historic register",
                "The property isn't on any historic register",
            ),
            f(
                f"{_WIND}(B)(10)",
                "not_in_open_space_easement",
                S,
                "no open space easement",
                "there's no open space easement on it",
            ),
            f(
                f"{_WIND}(B)(12)",
                "not_roof_mounted_on_residence",
                S,
                "ground-mounted",
                "Nothing is going on the roof of the house or the garage",
            ),
        ],
    )


def _sheet_020() -> FactSheet:
    """Public-project staging — filed as an accessory structure, as it was live.

    The §17.44.005 facts are the structure-siting questions the 2026-08-28 run
    asked and could not answer. The savings clause makes them irrelevant, and
    the rules have to be the thing that knows that.
    """
    return FactSheet(
        permit_type="accessory_structure",
        facts=[
            f(
                "17.44.200",
                "temporary_occupation_for_storage",
                S,
                "temporary parking of backhoes and stacking of pipe and plates",
                "to park two backhoes and stack pipe, conduit and shoring plates while the "
                "work is under way",
            ),
            f(
                "17.44.200",
                "public_project_nexus",
                S,
                "City replacement of the water main and sewer laterals",
                "The City's contractor is replacing the water main and the sewer laterals on "
                "our block",
            ),
            f(
                "17.44.200",
                "landowner_consent",
                S,
                "the owner-occupant signed the access letter",
                "I've signed their access letter agreeing to it - I own and occupy the property",
            ),
            f(
                "17.44.200",
                "council_permission_for_stated_time",
                S,
                "120 days",
                "The City Council granted permission for this staging area at its meeting on "
                "the 3rd, for a stated period of 120 days",
            ),
            f("17.44.005(B)(1)", "primary_dwelling_on_lot", A),
            f("17.44.005(D)(1)(b)1.b.", "new_detached_adu_square_feet", A),
            f("17.44.005(E)(3)(a)", "side_and_rear_setback", A),
        ],
    )


FACT_SHEETS: dict[str, FactSheet] = {
    "golden-001-maria-bakery-compliant-approve": _sheet_001(),
    "golden-002-maria-bakery-nonresident-helper-deny": _sheet_002(),
    "golden-003-home-occupation-illuminated-sign-deny": _sheet_003(),
    "golden-004-home-occupation-rooms-unclear-request-info": _sheet_004(),
    "golden-005-furniture-shop-outside-lumber-deny": _sheet_005(),
    "golden-006-garage-adu-oversized-addition-two-foot-setback-deny": _sheet_006(),
    "golden-007-detached-backyard-adu-640sf-within-limits-approve": _sheet_007(),
    "golden-008-bed-breakfast-two-rooms-floor-area-unstated-request-info": _sheet_008(),
    "golden-009-gas-tank-residential-deny": _sheet_009(),
    "golden-010-game-court-interior-lot-setbacks-approve": _sheet_010(),
    "golden-011-large-daycare-nearby-facility-request-info": _sheet_011(),
    "golden-012-cannabis-twelve-plants-shed-deny": _sheet_012(),
    "golden-013-cannabis-four-plants-shed-approve": _sheet_013(),
    "golden-014-home-bakery-predawn-hours-request-info": _sheet_014(),
    "golden-015-satellite-dish-under-threshold-approve": _sheet_015(),
    "golden-016-home-recycling-dropoff-driveway-deny": _sheet_016(),
    "golden-017-ham-antenna-height-omitted-request-info": _sheet_017(),
    "golden-018-garage-indoor-swap-meet-deny": _sheet_018(),
    "golden-019-wind-turbine-lot-size-request-info": _sheet_019(),
    "golden-020-public-project-staging-storage-approve": _sheet_020(),
}

GOLDEN_CASES = load_all()


# Permit config is deliberately None throughout: what decides these cases is
# the statute, not the office's outcome allow-list.
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_every_golden_case_has_a_fact_sheet(case: EvalCase) -> None:
    assert case.id in FACT_SHEETS, f"no hand-authored fact sheet for {case.id}"


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_rules_reach_the_expected_outcome_and_citations(case: EvalCase) -> None:
    """The bar: 20/20 on outcome, with the required section cited every time."""
    result = decide(FACT_SHEETS[case.id], None, corpus_dir=CORPUS_DIR)

    assert result.outcome is case.expected.outcome, (
        f"{case.id}: rules returned {result.outcome.value}, "
        f"expected {case.expected.outcome.value} - {result.rationale}"
    )
    cited = {citation.chunk_id for citation in result.citations}
    missing = set(case.expected.required_citations) - cited
    assert not missing, f"{case.id}: required citations {sorted(missing)} not cited (got {cited})"


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_request_info_names_what_is_missing(case: EvalCase) -> None:
    """A request_info that names nothing is not a request — it is a shrug."""
    result = decide(FACT_SHEETS[case.id], None, corpus_dir=CORPUS_DIR)
    if case.expected.outcome is DeterminationOutcome.REQUEST_INFO:
        assert result.missing_elements
        assert result.confidence == pytest.approx(0.8)
    else:
        assert not result.missing_elements
        assert result.confidence == pytest.approx(1.0)


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_every_fact_quote_is_verbatim_from_the_fixture(case: EvalCase) -> None:
    """A fact sheet may not contain a fact the applicant never wrote."""
    document = "\n\n".join((REPO_ROOT / doc).read_text(encoding="utf-8") for doc in case.docs)
    normalized = " ".join(document.split())
    for fact in FACT_SHEETS[case.id].facts:
        if not fact.quote:
            continue
        assert " ".join(fact.quote.split()) in normalized, (
            f"{case.id}: {fact.provision} quotes text not in the fixture: {fact.quote!r}"
        )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_every_fact_names_a_registered_element(case: EvalCase) -> None:
    """A typo must not quietly delete an element from the checklist."""
    for fact in FACT_SHEETS[case.id].facts:
        eid = f"{fact.section_id}/{fact.element}"
        element = element_by_eid(eid)
        assert element is not None, f"{case.id}: {eid} is not a registered element"
        assert element.provision == fact.provision, (
            f"{case.id}: {eid} is {element.provision}, fact says {fact.provision}"
        )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.id for c in GOLDEN_CASES])
def test_decisions_are_deterministic(case: EvalCase) -> None:
    """The property the model could not provide: same facts, same ruling."""
    sheet = FACT_SHEETS[case.id]
    first = decide(sheet, None, corpus_dir=CORPUS_DIR)
    for _ in range(4):
        assert decide(sheet, None, corpus_dir=CORPUS_DIR).model_dump() == first.model_dump()


@pytest.mark.parametrize(
    "eid",
    [element.eid for section in SECTIONS.values() for element in section.elements],
)
def test_every_rule_quote_is_a_unique_verbatim_span_of_its_section(eid: str) -> None:
    """Rules cite the corpus, so the corpus has to still say what they claim."""
    element = element_by_eid(eid)
    assert element is not None
    text = (CORPUS_DIR / f"{element.section_id}.txt").read_text(encoding="utf-8")
    assert " ".join(text.split()).count(" ".join(element.quote.split())) == 1, (
        f"{eid}: quote is not a unique span of {element.section_id}"
    )
    span = verbatim_span(text, element.quote)
    assert span is not None and span in text


def test_citations_verify_under_the_same_rule_the_verifier_uses() -> None:
    """Every citation the rules emit passes §7.3 steps 1 and 2 by construction."""
    for case in GOLDEN_CASES:
        result = decide(FACT_SHEETS[case.id], None, corpus_dir=CORPUS_DIR)
        for citation in result.citations:
            section_file: Path = CORPUS_DIR / f"{citation.chunk_id}.txt"
            assert section_file.exists()
            haystack = " ".join(section_file.read_text(encoding="utf-8").split())
            assert " ".join(citation.quote.split()) in haystack
