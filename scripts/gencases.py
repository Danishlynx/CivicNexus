"""Generate the PermitBench dataset from checked-in templates (§9.1).

Reads ``evals/permitbench/templates.json`` (curated case definitions — the
adversarially verified ground truth), fills PII placeholders with faker under
a FIXED seed, plants a canary in every phone number, and writes the case YAMLs
plus application documents. Deterministic: same templates + seed → same
dataset, byte for byte. PDF documents join in Phase 5 with the adversarial
set; Phase 2 documents are text (recorded in docs/eval-report.md context).
"""

import json
from pathlib import Path

import yaml
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[1]
PERMITBENCH = REPO_ROOT / "evals" / "permitbench"
TEMPLATES = PERMITBENCH / "templates.json"
CASES_DIR = PERMITBENCH / "cases"
DOCS_DIR = PERMITBENCH / "docs"
SEED = 4242


def main() -> int:
    templates = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    faker = Faker("en_US")
    Faker.seed(SEED)

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for index, template in enumerate(templates, 1):
        case_id = f"golden-{index:03d}-{template['slug']}"
        name = faker.name()
        first = name.split()[0].lower()
        email = f"{first}.{faker.last_name().lower()}@example.test"
        address = f"{faker.building_number()} {faker.street_name()} (synthetic)"
        phone = f"CANARY-{case_id}-{faker.msisdn()[:7]}"

        email_body = (
            template["scenario_email"]
            .replace("{NAME}", name)
            .replace("{EMAIL}", email)
            .replace("{ADDRESS}", address)
            .replace("{PHONE}", phone)
        )
        doc_text = (
            f"From: {name} <{email}>\n"
            f"To: permits@civicnexus-demo.test\n"
            f"Subject: permit application\n\n"
            f"{email_body}\n\n"
            f"Phone: {phone}\n"
        )
        doc_path = DOCS_DIR / f"{case_id}.txt"
        doc_path.write_text(doc_text, encoding="utf-8", newline="\n")

        case_yaml = {
            "id": case_id,
            "permit_type": template["permit_type"],
            "docs": [str(doc_path.relative_to(REPO_ROOT)).replace("\\", "/")],
            "applicant_profile": {"name": name, "email": email, "address": address},
            "expected": {
                "outcome": template["expected_outcome"],
                "required_citations": template["required_citations"],
                "must_request": template.get("must_request", []),
            },
            "tags": template.get("tags", []),
        }
        (CASES_DIR / f"{case_id}.yaml").write_text(
            yaml.safe_dump(case_yaml, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )
        print(f"gencases: wrote {case_id}")

    print(f"gencases: {len(templates)} cases generated (seed {SEED})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
