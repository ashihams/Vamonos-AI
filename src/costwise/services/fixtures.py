"""Fetch fixture companies once, then label them and pick a stratified held-out split."""

import logging
import random
from collections.abc import Mapping, Sequence

from costwise.domain.errors import ConfigError, DataSourceError
from costwise.domain.frozen import FrozenModel
from costwise.domain.icp import IcpRule, classify_difficulty, label_company
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import Difficulty, Split
from costwise.ports.data import CompanyDataSource
from costwise.ports.fixtures import FixtureStore

_LOG = logging.getLogger(__name__)
_MIN_PER_DIFFICULTY = 2


class BuildReport(FrozenModel):
    """Domains fetched now, skipped because they were stored, or failed."""

    fetched: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[str, ...]


class FixtureService:
    """Builds and labels the stored company fixtures."""

    def __init__(self, store: FixtureStore) -> None:
        """Read and write fixtures through the store."""
        self._store = store

    def build(self, domains: Sequence[str], source: CompanyDataSource) -> BuildReport:
        """Fetch each new domain once and store it; failures are reported, not raised."""
        stored = set(self._store.domains())
        fetched: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []
        for domain in dict.fromkeys(domains):
            if domain in stored:
                skipped.append(domain)
                continue
            try:
                fetch = source.fetch(domain)
            except DataSourceError as exc:
                _LOG.warning("fixture fetch failed for %s: %s", domain, exc)
                failed.append(domain)
                continue
            self._store.save_fetch(domain, fetch)
            fetched.append(domain)
        return BuildReport(fetched=tuple(fetched), skipped=tuple(skipped), failed=tuple(failed))

    def label(self, rule: IcpRule, heldout_count: int, seed: int) -> dict[str, CompanyLabel]:
        """Label every stored company and save the labels."""
        records = {
            domain: self._store.load_fetch(domain).record for domain in self._store.domains()
        }
        difficulties = {
            domain: classify_difficulty(record, rule) for domain, record in records.items()
        }
        splits = choose_splits(difficulties, heldout_count, seed)
        labels = {
            domain: CompanyLabel(
                expected_fit=label_company(record, rule),
                difficulty=difficulties[domain],
                split=splits[domain],
            )
            for domain, record in records.items()
        }
        self._store.save_labels(labels)
        return labels


def choose_splits(
    difficulties: Mapping[str, Difficulty], heldout_count: int, seed: int
) -> dict[str, Split]:
    """Pick held-out domains by seeded shuffle so both splits contain EASY and HARD."""
    easy = sorted(domain for domain, level in difficulties.items() if level is Difficulty.EASY)
    hard = sorted(domain for domain, level in difficulties.items() if level is Difficulty.HARD)
    too_few = min(len(easy), len(hard)) < _MIN_PER_DIFFICULTY
    if too_few or not _MIN_PER_DIFFICULTY <= heldout_count <= len(difficulties) - 2:
        raise ConfigError(
            "cannot stratify the held-out split: need two EASY and two HARD companies "
            "and room for both splits"
        )
    rng = random.Random(seed)  # noqa: S311 - seeded sampling, not security
    rng.shuffle(easy)
    rng.shuffle(hard)
    hard_count = _hard_quota(len(easy), len(hard), heldout_count)
    heldout = set(hard[:hard_count]) | set(easy[: heldout_count - hard_count])
    return {domain: Split.HELDOUT if domain in heldout else Split.EVAL for domain in difficulties}


def _hard_quota(n_easy: int, n_hard: int, heldout_count: int) -> int:
    """Return the proportional HARD count, leaving at least one of each level in each split."""
    proportional = round(heldout_count * n_hard / (n_easy + n_hard))
    low = max(1, heldout_count - (n_easy - 1))
    high = min(n_hard - 1, heldout_count - 1)
    return min(max(proportional, low), high)
