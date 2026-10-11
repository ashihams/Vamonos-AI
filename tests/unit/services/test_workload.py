"""Deterministic workload with repeated domains."""

import pytest

from costwise.domain.errors import ConfigError
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import Difficulty, Split
from costwise.services.workload import WorkloadService


def _labels(count: int) -> dict[str, CompanyLabel]:
    """Return count EVAL labels plus one HELDOUT label."""
    labels = {
        f"c{i:02d}.com": CompanyLabel(
            expected_fit=True, difficulty=Difficulty.EASY, split=Split.EVAL
        )
        for i in range(count)
    }
    labels["held.com"] = CompanyLabel(
        expected_fit=False, difficulty=Difficulty.HARD, split=Split.HELDOUT
    )
    return labels


def test_same_seed_gives_the_same_requests() -> None:
    """Order, ids, and splits are identical for a fixed seed and differ for another."""
    service = WorkloadService()
    first = service.build(_labels(50), 60, 0.25, seed=42)
    assert first == service.build(_labels(50), 60, 0.25, seed=42)
    assert first != service.build(_labels(50), 60, 0.25, seed=43)
    assert [request.task_id for request in first[:2]] == ["task-0001", "task-0002"]
    assert all(request.data_cache_hit is False for request in first)
    labels = _labels(50)
    assert all(request.split is labels[request.domain].split for request in first)


def test_repeats_follow_an_earlier_request_for_the_same_domain() -> None:
    """Exactly round(n * ratio) requests repeat a domain already seen."""
    requests = WorkloadService().build(_labels(50), 60, 0.25, seed=3)
    seen: set[str] = set()
    repeats = 0
    for request in requests:
        if request.domain in seen:
            repeats += 1
        seen.add(request.domain)
    assert len(requests) == 60
    assert repeats == 15
    assert len(seen) == 45


def test_zero_repeat_ratio_uses_distinct_domains() -> None:
    """With no repeats every domain appears once."""
    requests = WorkloadService().build(_labels(10), 5, 0.0, seed=1)
    assert len({request.domain for request in requests}) == 5


@pytest.mark.parametrize(
    ("count", "n_requests", "ratio", "message"),
    [
        (5, 0, 0.0, "n_requests"),
        (5, 10, 1.0, "repeat_ratio"),
        (5, 10, -0.1, "repeat_ratio"),
        (5, 20, 0.25, "distinct domains"),
        (5, 1, 0.6, "distinct domains"),
    ],
)
def test_invalid_workloads_raise(count: int, n_requests: int, ratio: float, message: str) -> None:
    """Bad sizes, ratios, or too few labeled domains raise ConfigError."""
    with pytest.raises(ConfigError, match=message):
        WorkloadService().build(_labels(count), n_requests, ratio, seed=1)
