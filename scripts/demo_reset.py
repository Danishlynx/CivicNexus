"""ADR-005 §7.2: reset the hot-add demo fixture for a clean BEFORE moment.

Deletes EXACTLY registry_agents/tree-preservation@1.0.0 — the demo's own
synthetic fixture card — and nothing else (guarded). Data deletion is
ASK-FIRST under the Working Agreement: human approved this script for demo
resets on 2026-08-26 ("fix it and make it work" ratification of ADR-005
§7.2); it still refuses to run without --confirm.
"""

import argparse
import os
import sys

FIXTURE_DOC = "tree-preservation@1.0.0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="actually delete the fixture card")
    args = parser.parse_args()
    if not args.confirm:
        print("demo_reset: refusing without --confirm (deletes the demo fixture card only)")
        return 1

    from google.cloud import firestore

    db = firestore.Client(project=os.environ.get("PROJECT_ID"))
    ref = db.collection("registry_agents").document(FIXTURE_DOC)
    snapshot = ref.get()
    if not snapshot.exists:
        print(f"demo_reset: {FIXTURE_DOC} not present (already clean)")
        return 0
    data = snapshot.to_dict() or {}
    if data.get("agent_id") != "tree-preservation":
        print(
            f"demo_reset: SAFETY STOP - doc is not the fixture card: {data.get('agent_id')}",
            file=sys.stderr,
        )
        return 1
    ref.delete()
    print(f"demo_reset: deleted fixture card {FIXTURE_DOC} (status was {data.get('status')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
