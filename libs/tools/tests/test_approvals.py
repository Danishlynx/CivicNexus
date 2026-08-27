"""Unit tests: approval store and the strengthened §4 approvals guard (no GCP).

ADR-007 D3 / ask A6 (ratified 2026-08-27): transitions into ISSUED/DENIED must
cite a REAL ``approvals/`` row naming this case and this target. The pure
verification logic is exercised here with fakes; the transactional wiring is
covered by the emulator tests and by ``scripts/verify_phase6.py`` against the
deployed clerk service.
"""

from typing import Any

import pytest
from civicnexus.contracts import Actor, Approval, CaseState
from civicnexus.tools import (
    ApprovalRequiredError,
    ApprovalStore,
    CaseStore,
    verify_approval_row,
)

TRACEPARENT = "00-" + "ab" * 16 + "-" + "cd" * 8 + "-01"


class _FakeSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], key: str) -> None:
        self._store = store
        self._key = key

    def create(self, data: dict[str, Any]) -> None:
        if self._key in self._store:
            raise RuntimeError(f"already exists: {self._key}")
        self._store[self._key] = data

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._store.get(self._key))


class _FakeDb:
    """Fake enough for ApprovalStore; has NO ``transaction`` attribute, so any
    test reaching CaseStore's transactional path fails loudly instead of
    silently passing."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, _name: str) -> "_FakeDb":
        return self

    def document(self, key: str) -> _FakeDoc:
        return _FakeDoc(self.docs, key)


class _RefusingPublisher:
    """The reader-mode publisher shape: publishing is a bug, not a no-op."""

    def publish(self, envelope: Any) -> str:
        raise AssertionError("no event may be published by these tests")


def _mint(store: ApprovalStore, case_id: str = "case-77") -> Approval:
    return store.mint(
        case_id=case_id,
        action="issue",
        target_state=CaseState.ISSUED,
        approver="danishlynx@gmail.com",
        traceparent=TRACEPARENT,
    )


class TestApprovalContract:
    def test_unnamed_approver_refused(self) -> None:
        with pytest.raises(ValueError, match="human approver"):
            Approval(
                approval_id="apr-1",
                case_id="case-1",
                action="issue",
                target_state=CaseState.ISSUED,
                approver="   ",
                approval_token="tok",
                traceparent=TRACEPARENT,
            )

    def test_blank_action_refused(self) -> None:
        with pytest.raises(ValueError, match="action"):
            Approval(
                approval_id="apr-1",
                case_id="case-1",
                action="",
                target_state=CaseState.DENIED,
                approver="clerk@city.test",
                approval_token="tok",
                traceparent=TRACEPARENT,
            )

    def test_non_approval_target_refused(self) -> None:
        # APPROVED is human-gated but NOT approval-row-gated (§4); an approvals
        # row claiming it would misrepresent the guard, so the contract refuses.
        with pytest.raises(ValueError, match="approvals exist only for"):
            Approval(
                approval_id="apr-1",
                case_id="case-1",
                action="approve",
                target_state=CaseState.APPROVED,
                approver="clerk@city.test",
                approval_token="tok",
                traceparent=TRACEPARENT,
            )


class TestApprovalStore:
    def test_mint_and_get_round_trip(self) -> None:
        store = ApprovalStore(_FakeDb())
        minted = _mint(store)
        loaded = store.get(minted.approval_id)
        assert loaded == minted
        assert loaded.case_id == "case-77"
        assert loaded.target_state is CaseState.ISSUED

    def test_tokens_and_ids_are_unique_and_nontrivial(self) -> None:
        store = ApprovalStore(_FakeDb())
        a, b = _mint(store), _mint(store)
        assert a.approval_id != b.approval_id
        assert a.approval_token != b.approval_token
        # token_urlsafe(32) yields ~43 url-safe chars; anything short is a bug
        assert len(a.approval_token) >= 40

    def test_get_missing_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            ApprovalStore(_FakeDb()).get("apr-missing")


class TestVerifyApprovalRow:
    def test_happy_path_passes_silently(self) -> None:
        store = ApprovalStore(_FakeDb())
        minted = _mint(store)
        verify_approval_row(store, minted.approval_id, case_id="case-77", target=CaseState.ISSUED)

    def test_empty_id_refused(self) -> None:
        with pytest.raises(ApprovalRequiredError, match="requires an approvals/ row id"):
            verify_approval_row(
                ApprovalStore(_FakeDb()), None, case_id="case-77", target=CaseState.ISSUED
            )

    def test_fabricated_id_refused(self) -> None:
        # The exact bypass A6 exists to close: a non-empty string with no row.
        with pytest.raises(ApprovalRequiredError, match="does not exist"):
            verify_approval_row(
                ApprovalStore(_FakeDb()),
                "apr-fabricated",
                case_id="case-77",
                target=CaseState.ISSUED,
            )

    def test_wrong_case_refused(self) -> None:
        store = ApprovalStore(_FakeDb())
        minted = _mint(store, case_id="case-OTHER")
        with pytest.raises(ApprovalRequiredError, match="names case case-OTHER"):
            verify_approval_row(
                store, minted.approval_id, case_id="case-77", target=CaseState.ISSUED
            )

    def test_wrong_target_refused(self) -> None:
        store = ApprovalStore(_FakeDb())
        minted = _mint(store)  # authorizes ISSUED
        with pytest.raises(ApprovalRequiredError, match="authorizes ISSUED, not DENIED"):
            verify_approval_row(
                store, minted.approval_id, case_id="case-77", target=CaseState.DENIED
            )


class TestCaseStoreApprovalInjection:
    """The injected guard fires before any transaction is attempted: _FakeDb has
    no ``transaction`` attribute, so if these transitions got past the guard the
    tests would fail with AttributeError, not pass silently."""

    def _store(self, db: _FakeDb, approvals: ApprovalStore) -> CaseStore:
        return CaseStore(
            db,
            _RefusingPublisher(),  # type: ignore[arg-type]
            Actor(agent_id="test", agent_version="0.0.0"),
            approvals=approvals,
        )

    def test_fabricated_string_no_longer_passes(self) -> None:
        from civicnexus.contracts import EventType

        db = _FakeDb()
        cs = self._store(db, ApprovalStore(db))
        with pytest.raises(ApprovalRequiredError, match="does not exist"):
            cs.transition(
                "case-77",
                CaseState.ISSUED,
                EventType.ACTION_APPROVED,
                traceparent=TRACEPARENT,
                approval_id="apr-fabricated",
            )
        assert db.docs == {}  # nothing written, nothing published

    def test_row_for_wrong_case_refused(self) -> None:
        from civicnexus.contracts import EventType

        db = _FakeDb()
        approvals = ApprovalStore(db)
        minted = _mint(approvals, case_id="case-OTHER")
        cs = self._store(db, approvals)
        with pytest.raises(ApprovalRequiredError, match="names case case-OTHER"):
            cs.transition(
                "case-77",
                CaseState.ISSUED,
                EventType.ACTION_APPROVED,
                traceparent=TRACEPARENT,
                approval_id=minted.approval_id,
            )
