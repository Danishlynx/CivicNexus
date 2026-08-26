"""Generator determinism (ADR-006 D11).

Two properties are load-bearing. First, the 20 golden artifacts must be
byte-identical after any regeneration, so growing the drill corpus can never
silently move the measured dataset out from under a recorded eval number.
Second, drill artifacts — PDFs included — must regenerate byte-identically, so
a fixture that passed the $0 canary is the same fixture that rides a billed run.

These tests rewrite the real dataset rather than a copy: that is the point.
Regeneration is a no-op when the property holds, and leaves a visible diff in
the working tree when it does not.
"""

import hashlib
from pathlib import Path

import pytest

from scripts import gencases


def _fingerprint(*dirs: Path) -> dict[str, str]:
    """sha256 of every file in these directories, keyed by repo-relative path."""
    prints: dict[str, str] = {}
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                key = str(path.relative_to(gencases.REPO_ROOT)).replace("\\", "/")
                prints[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return prints


def test_goldens_are_byte_identical_after_regeneration() -> None:
    before = _fingerprint(gencases.CASES_DIR, gencases.DOCS_DIR)
    assert len(before) == 40, "expected 20 case YAMLs + 20 documents"
    gencases.generate_goldens()
    assert _fingerprint(gencases.CASES_DIR, gencases.DOCS_DIR) == before


def test_generating_drills_does_not_move_the_golden_byte_stream() -> None:
    """The drill corpus draws PII from its own seeded instance (D11)."""
    before = _fingerprint(gencases.CASES_DIR, gencases.DOCS_DIR)
    gencases.generate_drills()
    assert _fingerprint(gencases.CASES_DIR, gencases.DOCS_DIR) == before


@pytest.mark.skipif(
    not gencases.DRILL_TEMPLATES.exists(), reason="drill templates not authored yet"
)
def test_drills_are_byte_identical_after_regeneration() -> None:
    gencases.generate_drills()
    before = _fingerprint(gencases.DRILL_CASES_DIR, gencases.DRILL_DOCS_DIR)
    assert before, "drill templates exist but generated nothing"
    gencases.generate_drills()
    assert _fingerprint(gencases.DRILL_CASES_DIR, gencases.DRILL_DOCS_DIR) == before


def test_pdf_rendering_is_invariant_and_leaves_the_canary_searchable() -> None:
    """Re-proves D11's PDF assumptions against the installed reportlab."""
    who = {
        "name": "Synthetic Applicant",
        "email": "synthetic.applicant@example.test",
        "address": "1 Example Way (synthetic)",
        "phone": "CANARY-adv-000-5550100",
    }
    for family in ("white_text_pdf", "pdf_metadata", "image_embedded_text"):
        first = gencases._drill_pdf(family, who, "Application body line.", "embedded line")
        second = gencases._drill_pdf(family, who, "Application body line.", "embedded line")
        assert first == second, f"{family} is not byte-stable"
        assert who["phone"].encode() in first, f"{family} lost its searchable canary"
