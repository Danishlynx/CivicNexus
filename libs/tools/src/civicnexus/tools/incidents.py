"""Firestore-backed incident store (§3.2 ``incidents/``; ADR-006 D6).

Write-once records: an incident that fires twice under one id is a bug that
must surface, so ``record`` uses Firestore ``create`` (loud on duplicates),
mirroring the case store's create semantics. Resolution is human-only, mirrored
from the QUARANTINED case-state contract.
"""

from datetime import UTC, datetime

from civicnexus.contracts import Incident, IncidentStatus
from civicnexus.otel import get_logger

_log = get_logger("incidents")


class IncidentStore:
    """The only sanctioned reader/writer of ``incidents/`` documents."""

    def __init__(self, db: object, *, collection: str = "incidents") -> None:
        self._db = db
        self._collection = collection

    def record(self, incident: Incident) -> None:
        """Persist a new incident and emit its audit log line."""
        doc = self._db.collection(self._collection).document(incident.incident_id)  # type: ignore[attr-defined]
        doc.create(incident.model_dump(mode="json"))
        _log.info(
            f"incident recorded {incident.incident_id}",
            extra={
                "audit": True,
                "case_id": incident.case_id,
                "incident_id": incident.incident_id,
                "kind": incident.kind.value,
                "cause": incident.cause,
                "quarantine_uri": incident.quarantine_uri,
                "traceparent": incident.traceparent,
            },
        )

    def get(self, incident_id: str) -> Incident:
        snapshot = self._db.collection(self._collection).document(incident_id).get()  # type: ignore[attr-defined]
        if not snapshot.exists:
            raise KeyError(f"incident {incident_id} does not exist")
        return Incident.model_validate(snapshot.to_dict())

    def resolve(self, incident_id: str, *, resolved_by: str) -> Incident:
        """Mark an incident RESOLVED — a named human action, never a machine's."""
        if not resolved_by:
            raise ValueError("resolving an incident requires a named human actor")
        incident = self.get(incident_id)
        resolved = incident.model_copy(update={"status": IncidentStatus.RESOLVED})
        doc = self._db.collection(self._collection).document(incident_id)  # type: ignore[attr-defined]
        doc.update({"status": IncidentStatus.RESOLVED.value})
        _log.info(
            f"incident resolved {incident_id}",
            extra={
                "audit": True,
                "incident_id": incident_id,
                "resolved_by": resolved_by,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )
        return resolved
