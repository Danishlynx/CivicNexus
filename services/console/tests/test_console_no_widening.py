"""Source-level enforcement of ADR-007 D7 and D13.

These greps are the enforceable form of two claims that are otherwise only
documentation: the console never mutates Firestore directly (CaseStore stays
the single writer), and console code contains no path to a model, an engine,
or object storage - so even a code bug cannot widen the public service's
blast radius beyond what its IAM already refuses.
"""

from pathlib import Path

_SRC = Path(__file__).parents[1] / "src" / "console"

#: Firestore mutation spellings on a document/collection handle (D7). The
#: console goes through CaseStore/ApprovalStore/IncidentStore or not at all.
_FIRESTORE_MUTATIONS = (".update(", ".set(", ".create(", ".delete(", "ArrayUnion")

#: Model/engine/storage call surfaces (D13): no route may reach one, and the
#: absence of any call site is part of the public-exposure argument.
_FORBIDDEN_CAPABILITY_TOKENS = (
    "vertexai",
    "aiplatform",
    "agent_engines",
    "query_json",
    "verify_finding",
    "google.cloud.storage",
    "signed_url",
    "generate_signed",
)


def _source_files() -> list[Path]:
    files = sorted(_SRC.rglob("*.py"))
    assert files, f"no console source found under {_SRC}"
    return files


def test_console_source_never_mutates_firestore_directly() -> None:
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for token in _FIRESTORE_MUTATIONS:
            assert token not in text, f"{path.name} contains forbidden Firestore call {token!r}"


def test_console_source_has_no_model_engine_or_storage_path() -> None:
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_CAPABILITY_TOKENS:
            assert token not in text, f"{path.name} contains forbidden capability {token!r}"


def test_caller_identity_decoding_confined_to_clerk_module() -> None:
    # D2: platform-verified-token payload decoding is permitted ONLY in the
    # clerk-only module (mounted solely under CONSOLE_MODE=clerk); the read
    # surface must have no identity-trusting path at all.
    for path in _source_files():
        if path.name == "clerk.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "b64decode" not in text, f"{path.name} decodes tokens; forbidden on the console"
        assert "authorization" not in text.lower(), (
            f"{path.name} reads auth headers; only clerk.py may"
        )
