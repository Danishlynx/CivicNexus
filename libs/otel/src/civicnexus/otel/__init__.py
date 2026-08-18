"""Observability helpers. Services log through here — never bare ``print``.

Phase 0 ships structured JSON logging in the shape Cloud Logging parses
natively; OpenTelemetry tracing setup joins in Phase 1 when the first
long-lived services exist.
"""

from civicnexus.otel.logging import get_logger

__all__ = ["get_logger"]
