"""Unit tests: the simulated-inbox queue (no GCP)."""

from typing import Any

import pytest
from civicnexus.tools import InboxStore
from civicnexus.tools.inbox import MAX_RAW_CHARS


class _FakeSnapshot:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], key: str) -> None:
        self._store = store
        self._key = key

    def create(self, data: dict[str, Any]) -> None:
        if self._key in self._store:
            raise RuntimeError(f"already exists: {self._key}")
        self._store[self._key] = data

    def update(self, patch: dict[str, Any]) -> None:
        self._store[self._key].update(patch)


class _FakeQuery:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def stream(self) -> list[_FakeSnapshot]:
        return [_FakeSnapshot(d) for d in self._docs]


class _FakeDb:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, _name: str) -> "_FakeDb":
        return self

    def document(self, key: str) -> _FakeDoc:
        return _FakeDoc(self.docs, key)

    def where(self, field: str, op: str, value: Any) -> _FakeQuery:
        assert op == "=="
        return _FakeQuery([d for d in self.docs.values() if d.get(field) == value])

    def stream(self) -> list[_FakeSnapshot]:
        return [_FakeSnapshot(d) for d in self.docs.values()]


class TestInboxStore:
    def test_submit_and_consume_lifecycle(self) -> None:
        inbox = InboxStore(_FakeDb())
        sid = inbox.submit("From: a\n\nbody", source="console_form", submitted_by="clerk@x.test")
        queued = inbox.next_new()
        assert queued is not None and queued["submission_id"] == sid
        inbox.claim(sid)
        assert inbox.next_new() is None  # PROCESSING is not NEW
        inbox.finish(sid, case_id="case-123")
        assert inbox.next_new() is None

    def test_oldest_new_first(self) -> None:
        inbox = InboxStore(_FakeDb())
        first = inbox.submit("first", source="gmail", submitted_by="a@x.test")
        inbox.submit("second", source="gmail", submitted_by="a@x.test")
        queued = inbox.next_new()
        assert queued is not None and queued["submission_id"] == first

    def test_empty_submission_refused(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            InboxStore(_FakeDb()).submit("   ", source="gmail", submitted_by="a@x.test")

    def test_oversized_submission_refused_at_the_door(self) -> None:
        # Firestore caps documents at ~1 MiB; fail loudly on submit, never
        # crash the consumer later (2026-08-28 audit).
        with pytest.raises(ValueError, match="too large"):
            InboxStore(_FakeDb()).submit(
                "x" * (MAX_RAW_CHARS + 1), source="gmail", submitted_by="a@x.test"
            )

    def test_failure_records_reason_and_partial_case(self) -> None:
        db = _FakeDb()
        inbox = InboxStore(db)
        sid = inbox.submit("raw", source="gmail", submitted_by="a@x.test")
        inbox.claim(sid)
        inbox.fail(sid, reason="ValidationError: boom", case_id="case-partial")
        assert db.docs[sid]["status"] == "FAILED"
        assert "boom" in db.docs[sid]["failure"]
        assert db.docs[sid]["case_id"] == "case-partial"
        assert inbox.next_new() is None

    def test_requeue_stale_recovers_crashed_claims(self) -> None:
        # A consumer that died mid-drive leaves PROCESSING rows; the next
        # startup recovers them instead of stranding the application forever.
        inbox = InboxStore(_FakeDb())
        sid = inbox.submit("raw", source="gmail", submitted_by="a@x.test")
        inbox.claim(sid)
        assert inbox.next_new() is None
        assert inbox.requeue_stale() == [sid]
        queued = inbox.next_new()
        assert queued is not None and queued["submission_id"] == sid
