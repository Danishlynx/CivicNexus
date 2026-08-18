"""Refuse `make teardown` unless explicitly confirmed.

Judges may test the deployed stack until Oct 1, 2026 (CLAUDE.md) — tearing down
before then would sabotage the submission. Requires CONFIRM_TEARDOWN=YES.
"""

import os
import sys
from datetime import date

JUDGING_ENDS = date(2026, 10, 1)


def main() -> int:
    if os.environ.get("CONFIRM_TEARDOWN") != "YES":
        print(
            "guard_teardown: refusing. Set CONFIRM_TEARDOWN=YES to proceed.\n"
            f"Reminder: judges may test until {JUDGING_ENDS.isoformat()}.",
            file=sys.stderr,
        )
        return 1
    if date.today() < JUDGING_ENDS:
        print(
            f"guard_teardown: WARNING — today is before {JUDGING_ENDS.isoformat()}; "
            "judging may still be ongoing. Proceeding because CONFIRM_TEARDOWN=YES.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
