"""Firestore-backed approval store (§6.2/§6.4 as amended by ADR-007 D3).

Mints the ``approvals/`` row that the §4 guard requires for transitions into
ISSUED and DENIED, converting that guard from a docstring into a record a
judge can read. Mirrors the incident store: write-once ``create`` (loud on
duplicates), one ``audit: true`` log line. Rows are append-only — there is no
update or delete here; fixture cleanup in verification scripts goes through
the db handle directly and never through this store.

The ``approval_token`` is minted per §6.2 for a future consumer (no send path
exists today — ADR-007 D3 deliberately builds no consumption plumbing). It is
stored in the row and NEVER logged (prime directive 3).
"""

import secrets
import uuid
from typing import Any

from civicnexus.contracts import Approval, CaseState
from civicnexus.otel import get_logger

_log = get_logger("approvals")


class ApprovalStore:
    """The only sanctioned writer of ``approvals/`` rows."""

    def __init__(self, db: Any, *, collection: str = "approvals") -> None:
        self._db = db
        self._collection = collection

    def mint(
        self,
        *,
        case_id: str,
        action: str,
        target_state: CaseState,
        approver: str,
        traceparent: str,
    ) -> Approval:
        """Record one human approval and return the row.

        Field guards (named approver, approval-requiring target) live on the
        :class:`~civicnexus.contracts.Approval` contract, so an invalid row
        cannot even be constructed, let alone stored.
        """
        approval = Approval(
            approval_id=f"apr-{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            action=action,
            target_state=target_state,
            approver=approver,
            approval_token=secrets.token_urlsafe(32),
            traceparent=traceparent,
        )
        doc = self._db.collection(self._collection).document(approval.approval_id)
        doc.create(approval.model_dump(mode="json"))
        _log.info(
            f"approval minted {approval.approval_id}",
            extra={
                "audit": True,
                "approval_id": approval.approval_id,
                "case_id": approval.case_id,
                "action": approval.action,
                "target_state": approval.target_state.value,
                "approver": approval.approver,
                "traceparent": approval.traceparent,
            },
        )
        return approval

    def get(self, approval_id: str) -> Approval:
        snapshot = self._db.collection(self._collection).document(approval_id).get()
        if not snapshot.exists:
            raise KeyError(f"approval {approval_id} does not exist")
        return Approval.model_validate(snapshot.to_dict())
