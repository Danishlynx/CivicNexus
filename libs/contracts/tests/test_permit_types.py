"""Tests for the permit-type config schema and loader."""

from pathlib import Path

import pytest
from civicnexus.contracts import DeterminationOutcome
from civicnexus.contracts.permit_types import PermitTypeConfig, load_permit_types
from pydantic import ValidationError

REPO_CONFIG = Path(__file__).resolve().parents[3] / "config" / "permit_types.yaml"


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "permit_types.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_repo_config_is_valid() -> None:
    types = load_permit_types(REPO_CONFIG)
    assert "garage_conversion" in types
    cfg = types["garage_conversion"]
    assert "zoning" in cfg.required_capabilities
    assert DeterminationOutcome.APPROVE in cfg.allowed_outcomes
    assert cfg.sla_days > 0


def test_rejects_unknown_outcome(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "shed_permit:\n  required_capabilities: [zoning]\n"
        "  allowed_outcomes: [escalate]\n  sla_days: 7\n",
    )
    with pytest.raises(ValidationError):
        load_permit_types(p)


def test_rejects_empty_capabilities(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "shed_permit:\n  required_capabilities: []\n  allowed_outcomes: [approve]\n  sla_days: 7\n",
    )
    with pytest.raises(ValidationError):
        load_permit_types(p)


def test_rejects_unknown_fields(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "shed_permit:\n  required_capabilities: [zoning]\n"
        "  allowed_outcomes: [approve]\n  sla_days: 7\n  auto_approve: true\n",
    )
    with pytest.raises(ValidationError):
        load_permit_types(p)


def test_rejects_empty_file(tmp_path: Path) -> None:
    p = _write(tmp_path, "")
    with pytest.raises(ValueError, match="non-empty mapping"):
        load_permit_types(p)


def test_config_model_frozen() -> None:
    cfg = PermitTypeConfig(
        required_capabilities=["zoning"],
        allowed_outcomes=[DeterminationOutcome.APPROVE],
        sla_days=7,
    )
    with pytest.raises(ValidationError):
        cfg.sla_days = 30
