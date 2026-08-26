"""Generate the PermitBench dataset from checked-in templates (§9.1).

Reads ``evals/permitbench/templates.json`` (curated case definitions — the
adversarially verified ground truth), fills PII placeholders with faker under
a FIXED seed, plants a canary in every phone number, and writes the case YAMLs
plus application documents. Deterministic: same templates + seed → same
dataset, byte for byte.

Phase 5 adds the drill corpus (ADR-006 D8/D11) from its own templates file.
The golden byte-stream must not move when drills are generated, so drills draw
PII from a *separately seeded instance* rather than the shared class-level
generator, and their ids live in their own append-only ``adv-###`` namespace.
Drill PDFs are written with ``invariant=1`` and no compression so regeneration
is byte-identical, with the canary drawn as real text so byte-search finds it.
"""

import io
import json
import textwrap
from pathlib import Path
from typing import Any

import yaml
from faker import Faker
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

REPO_ROOT = Path(__file__).resolve().parents[1]
PERMITBENCH = REPO_ROOT / "evals" / "permitbench"
TEMPLATES = PERMITBENCH / "templates.json"
CASES_DIR = PERMITBENCH / "cases"
DOCS_DIR = PERMITBENCH / "docs"
SEED = 4242

DRILLS = PERMITBENCH / "drills"
DRILL_TEMPLATES = DRILLS / "templates.json"
DRILL_CASES_DIR = DRILLS / "cases"
DRILL_DOCS_DIR = DRILLS / "docs"

#: Drill PII comes from its own instance so the goldens' byte-stream cannot
#: move when the drill corpus grows (D11, enforced by a byte-identity test).
DRILL_SEED = 8484

#: Families whose mechanism is inherently PDF-borne; the rest carry as text.
PDF_FAMILIES = frozenset({"white_text_pdf", "pdf_metadata", "image_embedded_text"})


def _identity(faker: Faker, case_id: str) -> dict[str, str]:
    """Synthetic applicant fields, with the canary planted in the phone number."""
    name = faker.name()
    first = name.split()[0].lower()
    return {
        "name": name,
        "email": f"{first}.{faker.last_name().lower()}@example.test",
        "address": f"{faker.building_number()} {faker.street_name()} (synthetic)",
        "phone": f"CANARY-{case_id}-{faker.msisdn()[:7]}",
    }


def _fill(text: str, who: dict[str, str]) -> str:
    """Substitute the PII placeholders a template may carry."""
    return (
        text.replace("{NAME}", who["name"])
        .replace("{EMAIL}", who["email"])
        .replace("{ADDRESS}", who["address"])
        .replace("{PHONE}", who["phone"])
    )


def _email_document(who: dict[str, str], body: str) -> str:
    """The application as the simulated inbox would deliver it."""
    return (
        f"From: {who['name']} <{who['email']}>\n"
        f"To: permits@civicnexus-demo.test\n"
        f"Subject: permit application\n\n"
        f"{body}\n\n"
        f"Phone: {who['phone']}\n"
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))


def generate_goldens() -> int:
    """Write the 20 measured cases. Unchanged by design — a frozen byte-stream."""
    templates = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    faker = Faker("en_US")
    Faker.seed(SEED)

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for index, template in enumerate(templates, 1):
        case_id = f"golden-{index:03d}-{template['slug']}"
        who = _identity(faker, case_id)
        doc_path = DOCS_DIR / f"{case_id}.txt"
        _write_text(doc_path, _email_document(who, _fill(template["scenario_email"], who)))

        _write_yaml(
            CASES_DIR / f"{case_id}.yaml",
            {
                "id": case_id,
                "permit_type": template["permit_type"],
                "docs": [str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/")],
                "applicant_profile": {
                    "name": who["name"],
                    "email": who["email"],
                    "address": who["address"],
                },
                "expected": {
                    "outcome": template["expected_outcome"],
                    "required_citations": template["required_citations"],
                    "must_request": template.get("must_request", []),
                },
                "tags": template.get("tags", []),
            },
        )
        print(f"gencases: wrote {case_id}")

    print(f"gencases: {len(templates)} cases generated (seed {SEED})")
    return len(templates)


def _wrap(text: str, width: int) -> list[str]:
    """Wrap to rendered lines, preserving explicit breaks and never truncating.

    Fixture text must reach the artifact whole: a fixture that is screened as a
    95-character fragment is not the fixture the canary verified (ADR-006 D10).
    """
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width) or [""])
    return lines


def _drill_pdf(
    family: str,
    who: dict[str, str],
    body: str,
    embedded: str,
    metadata_field: str = "subject",
) -> bytes:
    """Render one PDF-borne drill fixture.

    ``invariant=1`` plus ``pageCompression=0`` make regeneration byte-identical
    (re-proved against the installed reportlab by the determinism test), and the
    canary is drawn as ordinary text so a byte-search over the file finds it.

    ``metadata_field`` routes the pdf_metadata family's text to the document
    information entry a given seed claims to ride in, so the three seeds differ
    in mechanism rather than only in wording.
    """
    buf = io.BytesIO()
    canvas = Canvas(buf, pagesize=LETTER, invariant=1, pageCompression=0)
    canvas.setTitle("permit application")
    if family == "pdf_metadata":
        canvas.setAuthor(embedded if metadata_field == "author" else who["name"])
        canvas.setSubject(embedded if metadata_field == "subject" else "permit application")
        canvas.setKeywords(
            embedded if metadata_field == "keywords" else "permit application drill fixture"
        )
    canvas.setFont("Helvetica", 11)
    text_object = canvas.beginText(72, 720)
    for line in _wrap(body, 95):
        text_object.textLine(line)
    text_object.textLine("")
    text_object.textLine(f"Phone: {who['phone']}")
    canvas.drawText(text_object)
    if family == "white_text_pdf":
        canvas.setFillColorRGB(1, 1, 1)
        hidden = canvas.beginText(72, 260)
        for line in _wrap(embedded, 95):
            hidden.textLine(line)
        canvas.drawText(hidden)
        canvas.setFillColorRGB(0, 0, 0)
    if family == "image_embedded_text":
        rendered = _wrap(embedded, 110)
        image = Image.new("RGB", (960, 26 * len(rendered) + 16), "white")
        draw = ImageDraw.Draw(image)
        for number, line in enumerate(rendered):
            draw.text((8, 8 + 26 * number), line, fill="black")
        height = 12 * len(rendered) + 8
        canvas.drawImage(ImageReader(image), 72, 250 - height, width=460, height=height)
    canvas.showPage()
    canvas.save()
    return buf.getvalue()


def generate_drills() -> int:
    """Write the drill corpus: injection fixtures, engine-path cases, cards."""
    if not DRILL_TEMPLATES.exists():
        print("gencases: no drill templates yet - skipping drill corpus")
        return 0

    templates = json.loads(DRILL_TEMPLATES.read_text(encoding="utf-8"))
    faker = Faker("en_US")
    faker.seed_instance(DRILL_SEED)

    DRILL_CASES_DIR.mkdir(parents=True, exist_ok=True)
    DRILL_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    index = 0
    written = 0

    for family in templates["injection_families"]:
        carrier = "pdf" if family["family"] in PDF_FAMILIES else "text"
        for seed_number, fixture in enumerate(family["seeds"], 1):
            index += 1
            drill_id = f"adv-{index:03d}-{fixture['slug']}"
            who = _identity(faker, drill_id)
            body = _fill(fixture["host_scenario"], who)
            embedded = _fill(fixture["embedded_instruction"], who)

            if carrier == "pdf":
                doc_path = DRILL_DOCS_DIR / f"{drill_id}.pdf"
                doc_path.write_bytes(
                    _drill_pdf(
                        family["family"],
                        who,
                        body,
                        embedded,
                        fixture.get("metadata_field", "subject"),
                    )
                )
            else:
                doc_path = DRILL_DOCS_DIR / f"{drill_id}.txt"
                _write_text(doc_path, _email_document(who, f"{body}\n\n{embedded}"))

            _write_yaml(
                DRILL_CASES_DIR / f"{drill_id}.yaml",
                {
                    "kind": "injection",
                    "id": drill_id,
                    "family": family["family"],
                    "seed": seed_number,
                    "carrier": carrier,
                    "doc": str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "expected_filter": family["expected_filter"],
                },
            )
            written += 1

    for case in templates["engine_path_cases"]:
        index += 1
        drill_id = f"adv-{index:03d}-{case['slug']}"
        who = _identity(faker, drill_id)
        doc_path = DRILL_DOCS_DIR / f"{drill_id}.txt"
        _write_text(doc_path, _email_document(who, _fill(case["scenario_email"], who)))

        _write_yaml(
            DRILL_CASES_DIR / f"{drill_id}.yaml",
            {
                "kind": case["kind"],
                "id": drill_id,
                "permit_type": case["permit_type"],
                "docs": [str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/")],
                "applicant_profile": {
                    "name": who["name"],
                    "email": who["email"],
                    "address": who["address"],
                },
                "expected_outcome": case["expected_outcome"],
                "must_request": case.get("must_request", []),
            },
        )
        written += 1

    for card in templates["registry_cards"]:
        index += 1
        drill_id = f"adv-{index:03d}-{card['slug']}"
        _write_yaml(
            DRILL_CASES_DIR / f"{drill_id}.yaml",
            {
                "kind": "tool_poisoning",
                "id": drill_id,
                "card_id": f"drill-poison-{card['card_slug']}",
                "version": card["version"],
                "impersonates": card["impersonates"],
                "rejection_reason": card["rejection_reason"],
            },
        )
        written += 1

    print(f"gencases: {written} drill artifacts generated (seed {DRILL_SEED})")
    return written


def main() -> int:
    """Regenerate both corpora. Goldens first, so their seed stream is untouched."""
    generate_goldens()
    generate_drills()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
