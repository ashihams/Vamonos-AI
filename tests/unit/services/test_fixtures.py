"""Fixture build, labeling, and the stratified held-out split."""

from decimal import Decimal

import pytest

from costwise.domain.errors import ConfigError
from costwise.domain.task import Difficulty, Split
from costwise.ports.data import CompanyFetch
from costwise.services.fixtures import FixtureService, choose_splits
from tests.testing_fakes import FakeCompanySource, InMemoryFixtureStore
from tests.unit.domain.builders import make_company, make_rule


def _fetch(domain: str, employees: int | None, stage: str = "series_a") -> CompanyFetch:
    """Build a fetch whose company is EASY when employees is mid-range and HARD when near 50."""
    record = make_company(employees, stage, 30).model_copy(update={"domain": domain})
    return CompanyFetch(record=record, raw={"domain": domain}, credits_used=Decimal("2"))


def _mixed_store(n_easy: int, n_hard: int) -> InMemoryFixtureStore:
    """Return a store with the requested number of EASY and HARD companies."""
    fetches = {f"easy{i}.com": _fetch(f"easy{i}.com", 300) for i in range(n_easy)}
    fetches |= {f"hard{i}.com": _fetch(f"hard{i}.com", 52) for i in range(n_hard)}
    return InMemoryFixtureStore(fetches)


def test_build_fetches_each_new_domain_once_and_reports_failures() -> None:
    """Duplicates are fetched once, stored domains are skipped, and failures continue."""
    store = InMemoryFixtureStore({"old.com": _fetch("old.com", 300)})
    source = FakeCompanySource({"a.com": _fetch("a.com", 300), "b.com": _fetch("b.com", 52)})
    report = FixtureService(store).build(
        ["a.com", "a.com", "old.com", "missing.com", "b.com"], source
    )
    assert report.fetched == ("a.com", "b.com")
    assert report.skipped == ("old.com",)
    assert report.failed == ("missing.com",)
    assert source.domains == ["a.com", "missing.com", "b.com"]
    assert store.domains() == ["a.com", "b.com", "old.com"]


def test_label_is_deterministic_and_saves_fit_difficulty_and_split() -> None:
    """The same store, rule, and seed give the same labels, saved to the store."""
    store = _mixed_store(6, 4)
    service = FixtureService(store)
    first = service.label(make_rule(), heldout_count=4, seed=42)
    second = service.label(make_rule(), heldout_count=4, seed=42)
    assert first == second
    assert store.load_labels() == first
    assert first["easy0.com"].expected_fit is True
    assert first["easy0.com"].difficulty is Difficulty.EASY
    assert first["hard0.com"].difficulty is Difficulty.HARD
    assert sum(1 for label in first.values() if label.split is Split.HELDOUT) == 4


@pytest.mark.parametrize(
    ("n_easy", "n_hard", "heldout"), [(2, 2, 2), (9, 2, 3), (2, 9, 9), (20, 5, 10)]
)
def test_both_splits_contain_easy_and_hard(n_easy: int, n_hard: int, heldout: int) -> None:
    """Every split has at least one EASY and one HARD domain, with the exact held-out size."""
    difficulties = {f"e{i}": Difficulty.EASY for i in range(n_easy)}
    difficulties |= {f"h{i}": Difficulty.HARD for i in range(n_hard)}
    splits = choose_splits(difficulties, heldout, seed=7)
    assert sum(1 for split in splits.values() if split is Split.HELDOUT) == heldout
    for split in Split:
        levels = {difficulties[domain] for domain, chosen in splits.items() if chosen is split}
        assert levels == {Difficulty.EASY, Difficulty.HARD}


def test_seed_changes_the_heldout_choice() -> None:
    """Different seeds can pick different held-out domains; the same seed cannot."""
    difficulties = {f"e{i}": Difficulty.EASY for i in range(10)}
    difficulties |= {f"h{i}": Difficulty.HARD for i in range(10)}
    picks = {
        seed: frozenset(
            d for d, s in choose_splits(difficulties, 4, seed).items() if s is Split.HELDOUT
        )
        for seed in range(5)
    }
    assert picks[0] == frozenset(
        d for d, s in choose_splits(difficulties, 4, 0).items() if s is Split.HELDOUT
    )
    assert len(set(picks.values())) > 1


@pytest.mark.parametrize(
    ("n_easy", "n_hard", "heldout"), [(1, 5, 2), (5, 1, 2), (3, 3, 1), (3, 3, 5)]
)
def test_split_rejects_impossible_stratification(n_easy: int, n_hard: int, heldout: int) -> None:
    """Too few of either level, too small, or too large a held-out set is a ConfigError."""
    difficulties = {f"e{i}": Difficulty.EASY for i in range(n_easy)}
    difficulties |= {f"h{i}": Difficulty.HARD for i in range(n_hard)}
    with pytest.raises(ConfigError, match="stratify"):
        choose_splits(difficulties, heldout, seed=1)
