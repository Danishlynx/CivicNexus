"""Adversarial drill corpus (ADR-006 D8), isolated from the measured PermitBench.

Kept in its own package with its own schema and loader so the frozen measured
runner (``evals/permitbench/schema.py`` + ``load_all``) never sees these cases
— the ADR-005 byte-identical eval-path constraint holds, and ``make eval-full``
loads only the 20 standard cases.
"""
