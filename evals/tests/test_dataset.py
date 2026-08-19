"""Dataset integrity tests: the golden cases must stay loadable and honest."""

from collections import Counter

from evals.permitbench.schema import REPO_ROOT, load_all


def test_twenty_cases_load_and_validate() -> None:
    cases = load_all()
    assert len(cases) == 20


def test_smoke_subset_is_twelve() -> None:
    assert len(load_all(tag="smoke")) == 12


def test_outcomes_are_mixed() -> None:
    counts = Counter(c.expected.outcome.value for c in load_all())
    assert set(counts) == {"approve", "deny", "request_info"}
    assert all(count >= 4 for count in counts.values())


def test_every_doc_carries_its_canary() -> None:
    for case in load_all():
        text = "".join((REPO_ROOT / d).read_text(encoding="utf-8") for d in case.docs)
        assert f"CANARY-{case.id}" in text, case.id


def test_no_real_looking_pii_domains() -> None:
    for case in load_all():
        assert case.applicant_profile["email"].endswith("@example.test"), case.id


def test_ids_unique_and_sorted_stable() -> None:
    ids = [c.id for c in load_all()]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
