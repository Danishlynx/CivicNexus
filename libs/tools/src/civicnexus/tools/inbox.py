"""Firestore-backed simulated-inbox queue (§6.2 "simulated inbox", ADR-007).

One queue, two feeders, one consumer: applications arrive either as a real
email spotted by ``scripts/inbox_watcher.py`` or as a clerk-console form
submission, land here as raw email-shaped text, and are consumed by the
watcher, which drives the intake → review pipeline. The inbox never sends
mail — receiving is the only direction (fixture rules).

Concurrency model, stated honestly (2026-08-28 audit): this is a
SINGLE-CONSUMER queue — one watcher per project, which is the designed demo
shape. The status flip prevents re-pickup by that consumer's own loop; it is
not a compare-and-swap, so running two watchers concurrently is unsupported.
``requeue_stale`` exists so a crashed consumer's claims are recovered at the
next startup instead of stranding submissions in PROCESSING forever.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from civicnexus.otel import get_logger

_log = get_logger("inbox")

STATUS_NEW = "NEW"
STATUS_PROCESSING = "PROCESSING"
STATUS_PROCESSED = "PROCESSED"
STATUS_FAILED = "FAILED"

#: Firestore documents cap at ~1 MiB; a real application email is a few KiB.
#: Enforced here so an oversized submission fails loudly at the door instead
#: of crashing the consumer later (2026-08-28 audit).
MAX_RAW_CHARS = 200_000


class InboxStore:
    """The only sanctioned reader/writer of ``inbox/`` documents."""

    def __init__(self, db: Any, *, collection: str = "inbox") -> None:
        self._db = db
        self._collection = collection

    def submit(
        self,
        raw: str,
        *,
        source: str,
        submitted_by: str,
        docs: list[str] | None = None,
        screened: bool = False,
    ) -> str:
        """Queue one raw application (email-shaped text). Returns the id.

        ``docs`` carries attachment provenance strings (name+hash+status);
        ``screened`` marks feeder-side screening already done (Gmail path),
        so the consumer knows whether the inbound screen is still owed.
        """
        if not raw.strip():
            raise ValueError("an application submission cannot be empty")
        if len(raw) > MAX_RAW_CHARS:
            raise ValueError(
                f"application submission too large ({len(raw)} chars > {MAX_RAW_CHARS})"
            )
        submission_id = f"sub-{uuid4().hex[:12]}"
        doc = self._db.collection(self._collection).document(submission_id)
        doc.create(
            {
                "submission_id": submission_id,
                "raw": raw,
                "source": source,
                "submitted_by": submitted_by,
                "status": STATUS_NEW,
                "submitted_at": datetime.now(UTC),
                "case_id": "",
                "docs": list(docs or []),
                "screened": screened,
            }
        )
        _log.info(
            f"application submitted {submission_id}",
            extra={
                "audit": True,
                "submission_id": submission_id,
                "source": source,
                "submitted_by": submitted_by,
            },
        )
        return submission_id

    def next_new(self) -> dict[str, Any] | None:
        """The oldest NEW submission, or None.

        Server-side status filter (automatic single-field index) so the poll
        reads only actionable rows, not the whole collection's raw bodies.
        """
        rows = [
            snapshot.to_dict()
            for snapshot in self._db.collection(self._collection)
            .where("status", "==", STATUS_NEW)
            .stream()
        ]
        new = [r for r in rows if r]
        new.sort(key=lambda r: r.get("submitted_at") or datetime.now(UTC))
        return new[0] if new else None

    def requeue_stale(self) -> list[str]:
        """Reset PROCESSING rows back to NEW (crashed-consumer recovery).

        Called at consumer startup, when no other consumer may exist
        (single-consumer model above); returns the requeued ids.
        """
        stale = [
            snapshot.to_dict()
            for snapshot in self._db.collection(self._collection)
            .where("status", "==", STATUS_PROCESSING)
            .stream()
        ]
        requeued: list[str] = []
        for row in stale:
            if not row:
                continue
            sid = row["submission_id"]
            self._set_status(sid, STATUS_NEW)
            requeued.append(sid)
            _log.warning(
                f"stale claim requeued {sid} (prior consumer did not finish)",
                extra={"audit": True, "submission_id": sid},
            )
        return requeued

    def claim(self, submission_id: str) -> None:
        self._set_status(submission_id, STATUS_PROCESSING)

    def finish(self, submission_id: str, *, case_id: str) -> None:
        doc = self._db.collection(self._collection).document(submission_id)
        doc.update({"status": STATUS_PROCESSED, "case_id": case_id})
        _log.info(
            f"application processed {submission_id}",
            extra={"audit": True, "submission_id": submission_id, "case_id": case_id},
        )

    def fail(self, submission_id: str, *, reason: str, case_id: str = "") -> None:
        doc = self._db.collection(self._collection).document(submission_id)
        doc.update({"status": STATUS_FAILED, "failure": reason[:500], "case_id": case_id})
        _log.warning(
            f"application processing failed {submission_id}",
            extra={"audit": True, "submission_id": submission_id, "case_id": case_id},
        )

    def _set_status(self, submission_id: str, status: str) -> None:
        self._db.collection(self._collection).document(submission_id).update({"status": status})
