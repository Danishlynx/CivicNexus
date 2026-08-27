"""Firestore-backed case store — the single writer of case state (§3.2, §4).

Guards enforced here, in order:
1. transition legality per the §4 state machine,
2. human-only sources (PENDING_HUMAN, QUARANTINED) require a human actor,
3. ISSUED and DENIED require an approvals-row id (§4: "no transition into
   ISSUED, DENIED, or any letter send without a row in approvals/") — and,
   when an ApprovalStore is injected (ADR-007 D3), the id must name a REAL
   row for this case and this target, so a fabricated string no longer passes.

Every successful mutation publishes exactly one event and emits one audit log
line (``audit: true`` routes it to BigQuery via the Terraform log sink).
"""

from datetime import UTC, datetime
from typing import Any

from civicnexus.contracts import (
    APPROVAL_REQUIRED_TARGETS,
    Actor,
    Case,
    CaseState,
    Determination,
    EventEnvelope,
    EventType,
    Timer,
    can_transition,
    is_human_only,
)
from civicnexus.otel import get_logger
from civicnexus.tools.approvals import ApprovalStore
from civicnexus.tools.events import EventPublisher

#: Single source of truth moved to contracts (ADR-007 D3); alias kept so this
#: module still reads as the enforcement site.
_APPROVAL_REQUIRED_TARGETS = APPROVAL_REQUIRED_TARGETS

_log = get_logger("case_store")


class TransitionError(Exception):
    """Base class for refused case transitions."""


class IllegalTransitionError(TransitionError):
    """The §4 state machine has no such edge."""


class HumanActionRequiredError(TransitionError):
    """Transitions out of this state are reserved for a named human."""


class ApprovalRequiredError(TransitionError):
    """Target state requires a recorded approval id (§4 guard)."""


def validate_transition(
    case: Case,
    target: CaseState,
    *,
    human_actor: bool,
    approval_id: str | None,
) -> None:
    """Raise a :class:`TransitionError` subclass if the §4 guards refuse this move."""
    if not can_transition(case.state, target):
        raise IllegalTransitionError(f"{case.state.value} -> {target.value} is not a legal edge")
    if is_human_only(case.state) and not human_actor:
        raise HumanActionRequiredError(
            f"leaving {case.state.value} is a human-only action (case {case.case_id})"
        )
    if target in _APPROVAL_REQUIRED_TARGETS and not approval_id:
        raise ApprovalRequiredError(
            f"transition into {target.value} requires an approvals/ row id (case {case.case_id})"
        )


def verify_approval_row(
    approvals: ApprovalStore,
    approval_id: str | None,
    *,
    case_id: str,
    target: CaseState,
) -> None:
    """Raise :class:`ApprovalRequiredError` unless ``approval_id`` names a real
    ``approvals/`` row for THIS case and THIS target (ADR-007 D3 / ask A6).

    This is the strengthened form of the §4 guard: with an
    :class:`ApprovalStore` injected, a fabricated string no longer passes.
    """
    if not approval_id:
        raise ApprovalRequiredError(
            f"transition into {target.value} requires an approvals/ row id (case {case_id})"
        )
    try:
        approval = approvals.get(approval_id)
    except KeyError as exc:
        raise ApprovalRequiredError(
            f"approval {approval_id} does not exist in approvals/ (case {case_id})"
        ) from exc
    if approval.case_id != case_id:
        raise ApprovalRequiredError(
            f"approval {approval_id} names case {approval.case_id}, not {case_id}"
        )
    if approval.target_state is not target:
        raise ApprovalRequiredError(
            f"approval {approval_id} authorizes {approval.target_state.value}, "
            f"not {target.value} (case {case_id})"
        )


class CaseStore:
    """The only sanctioned reader/writer of ``cases/`` documents."""

    def __init__(
        self,
        db: Any,
        publisher: EventPublisher,
        actor: Actor,
        *,
        collection: str = "cases",
        approvals: ApprovalStore | None = None,
    ) -> None:
        self._db = db
        self._publisher = publisher
        self._actor = actor
        self._collection = collection
        # ADR-007 D3 (ask A6, ratified 2026-08-27): when an ApprovalStore is
        # injected, transitions into ISSUED/DENIED verify the row is real.
        # When absent, behaviour is byte-identical to the pre-ADR-007 store.
        self._approvals = approvals

    def create_case(self, case: Case, *, traceparent: str) -> None:
        """Create a new case document and publish ``case.received``.

        Uses Firestore ``create`` (not ``set``): re-delivery of the same
        case id must fail loudly, never silently overwrite.
        """
        doc = self._db.collection(self._collection).document(case.case_id)
        doc.create(case.model_dump(mode="json"))
        self._emit(
            case_id=case.case_id,
            event_type=EventType.CASE_RECEIVED,
            traceparent=traceparent,
            payload={"permit_type": case.permit_type, "state": case.state.value},
            from_state=None,
            to_state=case.state,
        )

    def get_case(self, case_id: str) -> Case:
        snapshot = self._db.collection(self._collection).document(case_id).get()
        if not snapshot.exists:
            raise KeyError(f"case {case_id} does not exist")
        return Case.model_validate(snapshot.to_dict())

    def list_cases(self) -> tuple[list[Case], list[str]]:
        """Every case, newest-updated first, plus ids of documents that failed
        validation (ADR-007 D5).

        Sorted in Python — no composite Firestore index exists, and creating
        one is Terraform this phase does not need. Per-document tolerance is a
        MUST, not a nicety: ``Case`` is ``frozen=True, extra="forbid"``, so
        without it one stray field in one document would 500 the entire
        console queue. Skipped ids are RETURNED so the caller can say "N
        documents failed validation" instead of silently narrowing the queue.
        """
        from pydantic import ValidationError

        valid: list[Case] = []
        invalid: list[str] = []
        for snapshot in self._db.collection(self._collection).stream():
            try:
                valid.append(Case.model_validate(snapshot.to_dict()))
            except ValidationError:
                invalid.append(snapshot.id)
                # ids only (D8): the failing document may hold applicant
                # fields, so neither the doc nor the error detail is logged.
                _log.warning(
                    f"case document failed validation, excluded from listing: {snapshot.id}",
                    extra={"case_id": snapshot.id},
                )
        valid.sort(key=lambda c: c.updated_at, reverse=True)
        return valid, invalid

    def transition(
        self,
        case_id: str,
        target: CaseState,
        event_type: EventType,
        *,
        traceparent: str,
        human_actor: bool = False,
        approval_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Case:
        """Atomically move a case to ``target`` if every §4 guard passes."""
        from google.cloud import firestore

        if self._approvals is not None and target in _APPROVAL_REQUIRED_TARGETS:
            verify_approval_row(self._approvals, approval_id, case_id=case_id, target=target)

        doc_ref = self._db.collection(self._collection).document(case_id)
        transaction = self._db.transaction()

        @firestore.transactional
        def _move(txn: Any) -> Case:
            snapshot = doc_ref.get(transaction=txn)
            if not snapshot.exists:
                raise KeyError(f"case {case_id} does not exist")
            case = Case.model_validate(snapshot.to_dict())
            validate_transition(case, target, human_actor=human_actor, approval_id=approval_id)
            updated = case.model_copy(update={"state": target, "updated_at": datetime.now(UTC)})
            txn.update(doc_ref, {"state": target.value, "updated_at": updated.updated_at})
            return updated

        before = self.get_case(case_id).state
        updated: Case = _move(transaction)
        event_payload = dict(payload or {})
        if approval_id:
            event_payload["approval_id"] = approval_id
        self._emit(
            case_id=case_id,
            event_type=event_type,
            traceparent=traceparent,
            payload=event_payload,
            from_state=before,
            to_state=target,
        )
        return updated

    def add_determination(
        self, case_id: str, determination: Determination, *, traceparent: str
    ) -> None:
        """Append a determination and publish ``review.completed``."""
        from google.cloud import firestore

        doc_ref = self._db.collection(self._collection).document(case_id)
        doc_ref.update(
            {
                "determinations": firestore.ArrayUnion([determination.model_dump(mode="json")]),
                "updated_at": datetime.now(UTC),
            }
        )
        self._emit(
            case_id=case_id,
            event_type=EventType.REVIEW_COMPLETED,
            traceparent=traceparent,
            payload={
                "agent_id": determination.agent_id,
                "outcome": determination.outcome.value,
                "citations": [c.chunk_id for c in determination.citations],
            },
            from_state=None,
            to_state=None,
        )

    def add_timer(self, case_id: str, timer: Timer) -> None:
        """Append a §4 Timer to the case (scheduling is the caller's job —
        the FIRING is the §5 event, not the scheduling)."""
        from google.cloud import firestore

        doc_ref = self._db.collection(self._collection).document(case_id)
        doc_ref.update(
            {
                "timers": firestore.ArrayUnion([timer.model_dump(mode="json")]),
                "updated_at": datetime.now(UTC),
            }
        )

    def record_event_once(self, event_id: str) -> bool:
        """Transactionally claim ``event_id``; False means already processed (§5 dedup)."""
        from google.api_core import exceptions as gexc

        doc_ref = self._db.collection("event_dedup").document(event_id)
        try:
            doc_ref.create({"processed_at": datetime.now(UTC)})
        except (gexc.AlreadyExists, gexc.Conflict):
            return False  # genuinely a duplicate — the §5 dedup answer
        # Anything else (permissions, transport) must surface as itself, not
        # masquerade as "already processed" (ADR-005 loud-guard rule).
        return True

    def _emit(
        self,
        *,
        case_id: str,
        event_type: EventType,
        traceparent: str,
        payload: dict[str, Any],
        from_state: CaseState | None,
        to_state: CaseState | None,
    ) -> None:
        envelope = EventEnvelope(
            type=event_type,
            case_id=case_id,
            actor=self._actor,
            traceparent=traceparent,
            payload=payload,
        )
        message_id = self._publisher.publish(envelope)
        _log.info(
            f"{event_type.value} case={case_id}",
            extra={
                "audit": True,
                "case_id": case_id,
                "event_id": str(envelope.event_id),
                "event_type": event_type.value,
                "from_state": from_state.value if from_state else None,
                "to_state": to_state.value if to_state else None,
                "actor_id": self._actor.agent_id,
                "actor_version": self._actor.agent_version,
                "message_id": message_id,
                "traceparent": traceparent,
            },
        )
