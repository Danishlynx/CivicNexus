"""Deterministic decision layer: the model extracts facts, this code decides.

B-006 measured the problem precisely. Five full PermitBench runs at temperature
0 scored 80/70/80/65/70 percent on the same 20 cases, "4 of 5 misses had
CORRECT citations", and a Gemini 2.5 Pro ablation at the decision step scored
the same 15/20 as Flash with a *different* five misses. The law was being read
correctly and composed inconsistently, and a stronger model did not fix it —
"model tier is not the constraint" is recorded as measured, not assumed.

So the composition step stops being a generation. The extraction agent reports,
per statute element, what the applicant stated; :mod:`.rules` holds the
checklist, the applicability logic and the ordered decision rule as ordinary
Python; :func:`.decide.decide` cites the corpus for the result. Same facts,
same ruling, every run — which is what §17 asks of a legal reviewer and what a
sampled decoder cannot promise.

Selected at runtime by ``DECISION_MODE=code``; the default stays ``model``.
"""

from civicnexus.decision.decide import DecisionResult, UndecidableError, decide
from civicnexus.decision.facts import FactSheet, FactStatus, ProvisionFact
from civicnexus.decision.rules import (
    SECTIONS,
    SUPPRESSIONS,
    Element,
    ElementKind,
    RuleOutcome,
    apply_ordered_rule,
    evaluate,
    rule_for_permit_type,
)

__all__ = [
    "SECTIONS",
    "SUPPRESSIONS",
    "DecisionResult",
    "Element",
    "ElementKind",
    "FactSheet",
    "FactStatus",
    "ProvisionFact",
    "RuleOutcome",
    "UndecidableError",
    "apply_ordered_rule",
    "decide",
    "evaluate",
    "rule_for_permit_type",
]
