"""Groundedness verifier — the §7.3 hallucination gate.

Every determination must pass, in order: (1) every cited section exists in
the corpus; (2) every quoted span string-matches its section verbatim; (3) a
cheap structured entailment check confirms the citations support the outcome;
(4) the outcome is legal for the permit type; (5) a request_info finding is
rejected if the requested fact is already stated (machine-verified quote);
(6) a request_info finding is rejected if the stated facts already decide the
case — judged by Gemma with 2-of-2 self-agreement plus a machine-verified
deciding quote. First failure earns one retry with the critique attached; the
first-pass rate is a headline metric.
"""

from civicnexus.verifier.verify import VerifierReport, verify_finding

__all__ = ["VerifierReport", "verify_finding"]
