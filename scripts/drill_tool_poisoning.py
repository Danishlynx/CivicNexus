"""Tool-poisoning drill (ADR-006 D8 + D18): containment by registry lifecycle.

The other two adversarial classes are contained by screening (the 15 injection
fixtures) or by pipeline outcome (contradictory / out-of-scope). These three
artifacts are neither. They are **registry cards, never screened content**, so
Model Armor is deliberately not called anywhere in this file: a drill that
screened a card would be measuring the wrong control, and any MATCH it produced
would be an artifact that is not an injection fixture sitting next to the 15/15
denominator. Containment here is proven by the approval lifecycle refusing
them, and by nothing else.

Four assertions, in the order a poisoner would meet them:

  registered — ``RegistryStore.register()`` rewrites status to PENDING and
    clears ``status_changed_by`` whatever the payload claimed. Every drill card
    ships a self-asserted ``APPROVED`` and a self-asserted approver, so the
    rewrite is exercised rather than assumed.
  invisible — the coordinator's own ``fetch_approved_cards()`` (the function
    that builds one consult tool per card) and the store's approved-only query
    both return none of the drill ids. Guarded against a vacuous pass: an
    unfiltered read must contain all three cards first, so "none visible" can
    never be an empty or misdirected registry answering an empty question.
  unapprovable — ``can_change_status(PENDING -> APPROVED, human_actor=False)``
    is False, ``MACHINE_ALLOWED_CHANGES`` is exactly {APPROVED -> QUARANTINED},
    and the live store raises ``LifecycleError`` when a machine actor tries.
  reversible — D18: a try/finally deletes EXACTLY the ids this run created,
    each re-checked against the reserved ``drill-poison-`` prefix at the moment
    of deletion. A survivor is not cosmetic debt: D15's demo preflight and the
    eval preflight both assert this prefix is clear, so one leaked card blocks
    the next billed run. That is also why the drill refuses to START while any
    ``drill-poison-*`` card is present.

Cost is Firestore reads and writes over a handful of documents — no engine
query, no model call, nothing billed beyond free-tier document operations.
Deletion authority is the reserved prefix and nothing else.
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from civicnexus.contracts import AgentCard, AgentStatus, can_change_status
from civicnexus.contracts.registry import MACHINE_ALLOWED_CHANGES
from registry.store import COLLECTION, LifecycleError, RegistryStore

from evals.permitbench.drills import schema as drills

RUN_LOG = Path(".deploy/tool_poisoning_last_run.json")

#: Reserved namespace that bounds this drill's deletion authority (D18).
CARD_ID_PREFIX = drills.CARD_ID_PREFIX

#: What every drill card self-asserts, so register()'s rewrite is exercised
#: against a real claim rather than against a card that never made one.
CLAIMED_STATUS = AgentStatus.APPROVED
CLAIMED_APPROVER = "drill-self-asserted-approver"

#: Non-routable by construction. Even a lookalike that somehow became a tool
#: would have nothing to dispatch to; never a real engine resource name.
DRILL_ENDPOINT = "drill://tool-poisoning/{card_id}"

#: The single machine-permitted move (§7.2), asserted as an exact set so a
#: widened contract fails here rather than quietly enlarging the blast radius.
EXPECTED_MACHINE_CHANGES = frozenset({(AgentStatus.APPROVED, AgentStatus.QUARANTINED)})

_record: dict[str, Any] = {"steps": []}

#: Keys created by THIS run. Appended BEFORE the write, so a crash between
#: create and return still leaves the finally block an id to delete.
_created: list[str] = []


class DrillFailure(Exception):
    """An assertion failed; the message becomes the named cause on the FAIL line."""


def _log(name: str, **fields: Any) -> None:
    _record["steps"].append({"step": name, "at": datetime.now(UTC).isoformat(), **fields})
    print(f"poison: {name} {({k: str(v)[:120] for k, v in fields.items()}) if fields else ''}")


def _persist() -> None:
    """Write evidence BEFORE any parsing or assertion can raise."""
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text(json.dumps(_record, indent=2, default=str), encoding="utf-8", newline="\n")


def _key(card_id: str, version: str) -> str:
    """The Firestore document id for a card, mirroring ``AgentCard.key``."""
    return f"{card_id}@{version}"


def poison_card(case: drills.ToolPoisoningCard) -> AgentCard:
    """Build the lookalike a poisoner would submit, self-asserted claim included.

    The claimed capability is derived from the impersonated agent rather than
    invented: a lookalike claiming a capability nobody routes on would be
    invisible to the coordinator for an uninteresting reason, and the
    approved-only assertion would then prove nothing about the defense. The
    description carries the drill provenance so anyone reading the raw document
    in Firestore can see what it is without consulting this file.
    """
    target_agent_id, _, _ = case.impersonates.partition("@")
    return AgentCard(
        agent_id=case.card_id,
        version=case.version,
        display_name=f"{target_agent_id.replace('-', ' ').capitalize()} reviewer",
        description=(
            f"Synthetic tool-poisoning drill card (ADR-006 D8/D18) impersonating "
            f"{case.impersonates}; registered and deleted by "
            f"scripts/drill_tool_poisoning.py. {case.rejection_reason}"
        ),
        capabilities=[target_agent_id.replace("-", "_")],
        endpoint=DRILL_ENDPOINT.format(card_id=case.card_id),
        status=CLAIMED_STATUS,
        status_changed_by=CLAIMED_APPROVER,
    )


def load_poison_cases() -> list[drills.ToolPoisoningCard]:
    """The three tool-poisoning artifacts, re-checked against the reserved prefix.

    The schema pattern already pins the prefix, but the finally block's entire
    safety argument is "every id this drill touches starts with drill-poison-",
    so the drill states that as its own precondition instead of inheriting it
    silently from a regex in another module.
    """
    cases = [
        case
        for case in drills.load_all(drills.DrillKind.TOOL_POISONING)
        if isinstance(case, drills.ToolPoisoningCard)
    ]
    expected = drills.EXPECTED_CENSUS[drills.DrillKind.TOOL_POISONING]
    if len(cases) != expected:
        raise DrillFailure(f"expected {expected} tool-poisoning drill cases, loaded {len(cases)}")
    stray = sorted(c.card_id for c in cases if not c.card_id.startswith(CARD_ID_PREFIX))
    if stray:
        raise DrillFailure(f"drill card ids outside the reserved prefix: {', '.join(stray)}")
    return cases


def find_drill_cards(store: RegistryStore) -> list[str]:
    """Every ``drill-poison-*`` key currently in the registry, from any drill.

    Deliberately unfiltered by status and unfiltered by owner: the preflight
    question is "is this namespace clean", and a leaked card from the D12
    breaker drill corrupts an eval or demo preflight exactly as badly as one of
    ours would.
    """
    return sorted(c.key for c in store.find() if c.agent_id.startswith(CARD_ID_PREFIX))


def assert_registry_clear(store: RegistryStore) -> None:
    """Refuse to start while any drill card is present (D18, and D15's preflight).

    Reported, never auto-deleted: another drill's card is not ours to remove,
    and silently cleaning up would hide the fact that some previous run's
    finally block did not complete.
    """
    present = find_drill_cards(store)
    _record["preflight_drill_cards"] = present
    _persist()
    _log("preflight", drill_cards_present=present or "none")
    if present:
        raise DrillFailure(
            f"{len(present)} drill-poison-* card(s) already registered: {', '.join(present)} "
            "(a previous run's cleanup did not complete; --cleanup-only --confirm removes "
            "this drill's own ids)"
        )


def register_poison_cards(
    store: RegistryStore, cases: Sequence[drills.ToolPoisoningCard]
) -> list[dict[str, Any]]:
    """Register each lookalike and assert the lifecycle overrode its claim.

    Both the returned card and the persisted document are checked. The return
    value could be correct while the write was wrong, and the coordinator reads
    the document, never the return value — so the document is the one that has
    to say PENDING.
    """
    rows: list[dict[str, Any]] = []
    for case in cases:
        card = poison_card(case)
        _created.append(card.key)
        _record["created_keys"] = list(_created)
        _persist()

        registered = store.register(card)
        stored = store.get(card.agent_id, card.version)
        rows.append(
            {
                "drill_id": case.id,
                "key": card.key,
                "impersonates": case.impersonates,
                "claimed_status": CLAIMED_STATUS.value,
                "claimed_status_changed_by": CLAIMED_APPROVER,
                "returned_status": registered.status.value,
                "returned_status_changed_by": registered.status_changed_by,
                "stored_status": stored.status.value,
                "stored_status_changed_by": stored.status_changed_by,
                "rejection_reason": case.rejection_reason,
            }
        )
        _record["registered"] = rows
        _persist()
        _log("registered", key=card.key, claimed=CLAIMED_STATUS.value, stored=stored.status.value)

        if registered.status is not AgentStatus.PENDING:
            raise DrillFailure(f"{card.key}: register() returned {registered.status.value}")
        if stored.status is not AgentStatus.PENDING:
            raise DrillFailure(f"{card.key}: stored status is {stored.status.value}, not PENDING")
        if registered.status_changed_by or stored.status_changed_by:
            raise DrillFailure(
                f"{card.key}: the self-asserted approver survived registration "
                f"(returned={registered.status_changed_by!r} stored={stored.status_changed_by!r})"
            )
    return rows


def assert_invisible_to_coordinator(
    store: RegistryStore, drill_keys: Sequence[str]
) -> dict[str, Any]:
    """A PENDING lookalike must not reach the coordinator's toolset (the D8 defense).

    Two readers, because they are two different bugs: the store's own
    ``find(status=APPROVED)``, and ``caseflow_agent.registry_toolset``'s
    ``fetch_approved_cards()``, which is the function that actually builds the
    consult tools. The vacuity guard runs first — an unfiltered read must
    contain every key in ``drill_keys`` — because "none visible" from a
    registry that can see nothing at all would be a pass that proves nothing.
    """
    mode = os.environ.get("REGISTRY_MODE", "http")
    if mode == "http" and not os.environ.get("REGISTRY_URL", "").strip():
        raise DrillFailure(
            "REGISTRY_URL is unset under REGISTRY_MODE=http: fetch_approved_cards() would "
            "return [] without querying anything and the assertion would be vacuous"
        )

    population = sorted(c.key for c in store.find())
    missing = [key for key in drill_keys if key not in population]
    if missing:
        raise DrillFailure(
            f"drill cards absent from the unfiltered registry read ({', '.join(missing)}); "
            "an approved-only result would be vacuous"
        )
    approved_keys = sorted(c.key for c in store.find(status=AgentStatus.APPROVED))

    # Imported late, as the sibling drivers do: this pulls in the ADK toolset
    # module, which no other step of this drill needs.
    from caseflow_agent.registry_toolset import fetch_approved_cards

    toolset_keys = sorted(
        _key(str(card.get("agent_id", "")), str(card.get("version", "")))
        for card in fetch_approved_cards()
    )

    # Matched on agent_id, not the full key: an approved lookalike at ANY
    # version is a leak, including a version this run did not create.
    drill_ids = {key.partition("@")[0] for key in drill_keys}
    leaked = sorted(
        key for key in set(approved_keys) | set(toolset_keys) if key.partition("@")[0] in drill_ids
    )
    summary: dict[str, Any] = {
        "registry_mode": mode,
        "population": population,
        "store_approved": approved_keys,
        "toolset_approved": toolset_keys,
        "leaked": leaked,
    }
    _record["visibility"] = summary
    _persist()
    _log("visibility", mode=mode, approved=approved_keys or "none", leaked=leaked or "none")
    if leaked:
        raise DrillFailure(f"the approved-only query exposed drill card(s): {', '.join(leaked)}")
    return summary


def assert_no_machine_approval(store: RegistryStore, drill_keys: Sequence[str]) -> dict[str, Any]:
    """No machine actor can approve a card, by contract and against the live store.

    The contract check alone would pass against a store that never consulted
    it; the live check alone would not notice ``MACHINE_ALLOWED_CHANGES`` being
    widened for some other caller. Both, or the claim is wider than its test.
    """
    if can_change_status(AgentStatus.PENDING, AgentStatus.APPROVED, human_actor=False):
        raise DrillFailure("the contract permits a machine actor to move PENDING -> APPROVED")
    machine_changes = sorted(f"{a.value} -> {b.value}" for a, b in MACHINE_ALLOWED_CHANGES)
    if frozenset(MACHINE_ALLOWED_CHANGES) != EXPECTED_MACHINE_CHANGES:
        raise DrillFailure(
            f"MACHINE_ALLOWED_CHANGES is not APPROVED -> QUARANTINED only: {machine_changes}"
        )

    refusals: list[dict[str, str]] = []
    summary: dict[str, Any] = {
        "contract_machine_changes": machine_changes,
        "pending_to_approved_by_machine": False,
        "refusals": refusals,
    }
    for key in drill_keys:
        agent_id, _, version = key.partition("@")
        try:
            store.change_status(
                agent_id, version, AgentStatus.APPROVED, actor="", human_actor=False
            )
        except LifecycleError as exc:
            refusals.append({"key": key, "refused_with": str(exc)})
            _record["machine_approval"] = summary
            _persist()
            _log("machine-approval-refused", key=key)
        else:
            raise DrillFailure(f"{key}: the store APPROVED a drill card for a machine actor")
    _record["machine_approval"] = summary
    _persist()
    return summary


def delete_drill_cards(db: Any, keys: Sequence[str]) -> dict[str, Any]:
    """Delete exactly these cards, re-checking the prefix at the delete (D18).

    The guard is re-applied here rather than trusted from the caller because
    this is the only place the drill removes registry documents: if a future
    caller hands it a key it did not create, the refusal has to happen at the
    delete. Two guards, mirroring ``demo_reset.py``'s safety stop — the
    document id AND the stored ``agent_id`` must both carry the reserved
    prefix, so a key that merely looks right cannot remove a real card.
    Deletion is verified rather than assumed; a survivor is reported and fails
    the run.
    """
    deleted: list[str] = []
    refused: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    survived: list[str] = []
    for key in keys:
        if not key.startswith(CARD_ID_PREFIX):
            refused.append({"key": key, "reason": "outside the drill-poison- prefix"})
            continue
        try:
            ref = db.collection(COLLECTION).document(key)
            snapshot = ref.get()
            if not snapshot.exists:
                # Never created, or already removed: nothing left to delete.
                deleted.append(key)
                continue
            data: dict[str, Any] = snapshot.to_dict() or {}
            if not str(data.get("agent_id", "")).startswith(CARD_ID_PREFIX):
                refused.append({"key": key, "reason": f"stored agent_id {data.get('agent_id')!r}"})
                continue
            ref.delete()
            if ref.get().exists:
                survived.append(key)
            else:
                deleted.append(key)
        except Exception as exc:  # fail closed, but keep cleaning the remaining ids
            failed.append({"key": key, "error": f"{type(exc).__name__}: {exc}"})
    return {"deleted": deleted, "refused": refused, "failed": failed, "survived": survived}


def run_drill(store: RegistryStore, cases: Sequence[drills.ToolPoisoningCard]) -> dict[str, Any]:
    """The assertion body, wrapped by main()'s try/finally so cleanup always runs."""
    assert_registry_clear(store)
    registered = register_poison_cards(store, cases)
    keys = [str(row["key"]) for row in registered]
    visibility = assert_invisible_to_coordinator(store, keys)
    machine = assert_no_machine_approval(store, keys)
    return {"registered": registered, "visibility": visibility, "machine_approval": machine}


def report_cleanup(lifecycle: dict[str, Any]) -> None:
    """Print what the finally block actually removed — D18's reporting half."""
    deleted: list[str] = lifecycle["deleted"]
    print(f"poison: cleanup deleted {len(deleted)} drill card(s): {', '.join(deleted) or 'none'}")
    for entry in lifecycle["refused"]:
        print(f"  REFUSED (not this drill's to delete): {entry['key']} - {entry['reason']}")
    for entry in lifecycle["failed"]:
        print(f"  DELETE FAILED: {entry['key']} - {entry['error']}")
    for key in lifecycle["survived"]:
        print(f"  STILL PRESENT AFTER DELETE: {key}")


def cleanup_only(store: RegistryStore, db: Any, cases: Sequence[drills.ToolPoisoningCard]) -> int:
    """Remove this drill's own cards after a crash hard enough to skip the finally.

    Scoped to the ids in this drill's corpus, never a blanket prefix sweep:
    ``drill-poison-breaker`` belongs to the D12 breaker drill, and one drill
    deleting another's card is precisely the confusion the reserved prefix
    exists to prevent. Foreign ``drill-poison-*`` ids are reported and left
    alone, so the operator sees them and decides.
    """
    own = {_key(case.card_id, case.version) for case in cases}
    present = find_drill_cards(store)
    foreign = [key for key in present if key not in own]
    lifecycle = delete_drill_cards(db, sorted(own & set(present)))
    _record["lifecycle"] = lifecycle
    _record["foreign_drill_cards"] = foreign
    _record["finished_at"] = datetime.now(UTC).isoformat()
    _persist()
    report_cleanup(lifecycle)
    if foreign:
        print(f"poison: {len(foreign)} foreign drill card(s) LEFT UNTOUCHED: {', '.join(foreign)}")
    ok = not lifecycle["failed"] and not lifecycle["survived"] and not lifecycle["refused"]
    cause = "" if ok else " - cleanup did not complete; see the evidence file"
    print(
        f"{'PASS' if ok else 'FAIL'}: tool-poisoning-cleanup (removed "
        f"{len(lifecycle['deleted'])} of this drill's own card ids; {len(foreign)} foreign "
        f"id(s) reported, not deleted){cause}; evidence {RUN_LOG}"
    )
    return 0 if ok else 1


def main() -> int:
    """Run the drill under a try/finally and print a PASS/FAIL scoped to what ran."""
    # D15: interpolated API errors are not ascii-safe, and a smart quote in an
    # error body would raise UnicodeEncodeError on cp1252 mid-run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="delete only this drill's own drill-poison-* cards left by a crashed run, then exit",
    )
    parser.add_argument(
        "--confirm", action="store_true", help="required by --cleanup-only (data deletion)"
    )
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID", "").strip()
    if not project:
        print("FAIL: tool-poisoning - PROJECT_ID is not set")
        return 1
    _record["project"] = project
    _record["cleanup_only"] = args.cleanup_only
    _record["started_at"] = datetime.now(UTC).isoformat()
    _persist()

    if args.cleanup_only and not args.confirm:
        print("FAIL: tool-poisoning - --cleanup-only deletes documents; pass --confirm as well")
        return 1

    try:
        cases = load_poison_cases()
    except Exception as exc:
        _record["corpus_error"] = repr(exc)
        _persist()
        print(f"FAIL: tool-poisoning - drill corpus did not load: {exc}")
        return 1
    _log("corpus", cases=[c.id for c in cases])
    _persist()

    try:
        from google.cloud import firestore

        db: Any = firestore.Client(project=project)
        store = RegistryStore(db)
    except Exception as exc:
        _record["client_error"] = repr(exc)
        _persist()
        print(f"FAIL: tool-poisoning - Firestore client for {project} failed: {exc}")
        return 1

    if args.cleanup_only:
        return cleanup_only(store, db, cases)

    failure: str | None = None
    lifecycle: dict[str, Any] | None = None
    try:
        try:
            _record["result"] = run_drill(store, cases)
        finally:
            # D18, non-negotiable: this runs on an assertion failure, on an
            # unexpected exception and on success, deleting exactly the ids in
            # _created and nothing else.
            lifecycle = delete_drill_cards(db, list(_created))
            _record["lifecycle"] = lifecycle
            _persist()
            report_cleanup(lifecycle)
    except DrillFailure as exc:
        failure = str(exc)
    except Exception as exc:
        failure = f"unexpected {type(exc).__name__}: {exc}"

    leftover: list[str] = []
    deleted_count = 0
    if lifecycle is not None:
        deleted_count = len(lifecycle["deleted"])
        leftover = sorted({*lifecycle["survived"], *(e["key"] for e in lifecycle["failed"])})
    if failure is None and leftover:
        failure = f"D18 lifecycle incomplete; card(s) still registered: {', '.join(leftover)}"

    _record["failure"] = failure
    _record["finished_at"] = datetime.now(UTC).isoformat()
    _persist()

    if failure is not None:
        print(f"FAIL: tool-poisoning - {failure}; evidence {RUN_LOG}")
        return 1
    mode = os.environ.get("REGISTRY_MODE", "http")
    print(
        f"PASS: tool-poisoning ({len(cases)}/{len(cases)} lookalike cards forced to PENDING with "
        f"the self-asserted approver cleared; absent from the approved-only query via the store "
        f"and via the coordinator toolset in REGISTRY_MODE={mode}; machine approval refused by "
        f"the contract and by the live store; {deleted_count} card(s) deleted); "
        f"evidence {RUN_LOG}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
