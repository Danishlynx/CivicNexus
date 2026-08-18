"""PermitType configuration schema and loader (ARCHITECTURE.md §4).

``config/permit_types.yaml`` is the operator-editable file; this module is the
only sanctioned way to read it, so every service sees the same validated view.
"""

from pathlib import Path

import yaml
from civicnexus.contracts.determinations import DeterminationOutcome
from pydantic import BaseModel, ConfigDict, Field


class PermitTypeConfig(BaseModel):
    """Review requirements for one permit type, verbatim fields from §4."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required_capabilities: list[str] = Field(min_length=1)
    allowed_outcomes: list[DeterminationOutcome] = Field(min_length=1)
    sla_days: int = Field(gt=0)


def load_permit_types(path: Path) -> dict[str, PermitTypeConfig]:
    """Load and validate the permit-type config file.

    Raises on unknown fields, unknown outcomes, or empty capability lists —
    a malformed config must fail service startup, never limp along.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{path}: expected a non-empty mapping of permit types")
    return {name: PermitTypeConfig.model_validate(cfg) for name, cfg in raw.items()}
