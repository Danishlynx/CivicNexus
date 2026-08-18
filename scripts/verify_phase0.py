"""Phase 0 exit-criteria check beyond `make test` + `make smoke`.

ARCHITECTURE.md §11 Phase 0 exit: smoke green (checked by the Makefile chain)
and a Cloud Trace URL recorded in PROGRESS.md — this script asserts the latter.
"""

import re
import sys
from pathlib import Path

# A concrete trace must be recorded — a URL carrying a trace id, not a bare
# traces list link (which exists even when zero traces were emitted). Covers
# the legacy details/tid forms and the current Trace Explorer form
# (`explorer;...;traceId=<hex>` — observed live 2026-08-18).
TRACE_URL_PATTERN = re.compile(
    r"https://console\.cloud\.google\.com/traces/"
    r"(?:details/[0-9a-f]{16,32}|list\?\S*tid=[0-9a-f]{16,32}|explorer\S*traceId=[0-9a-f]{16,32})\S*",
    re.IGNORECASE,
)


def main() -> int:
    progress = Path("PROGRESS.md")
    if not progress.exists():
        print("verify_phase0: PROGRESS.md does not exist", file=sys.stderr)
        return 1
    match = TRACE_URL_PATTERN.search(progress.read_text(encoding="utf-8"))
    if not match:
        print(
            "verify_phase0: no Cloud Trace URL recorded in PROGRESS.md "
            "(expected a console.cloud.google.com/traces/... link)",
            file=sys.stderr,
        )
        return 1
    print(f"verify_phase0: trace URL recorded: {match.group(0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
