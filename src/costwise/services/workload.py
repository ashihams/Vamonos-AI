"""Deterministic request order with a controlled share of repeated domains."""

import random
from collections.abc import Mapping

from costwise.domain.errors import ConfigError
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import QualificationRequest


class WorkloadService:
    """Builds the ordered requests an evaluation runs."""

    def build(
        self,
        labels: Mapping[str, CompanyLabel],
        n_requests: int,
        repeat_ratio: float,
        seed: int,
    ) -> tuple[QualificationRequest, ...]:
        """Return n_requests requests where round(n_requests * repeat_ratio) repeat a domain.

        Each repeat is inserted after at least one earlier request for the same
        domain. ``data_cache_hit`` is always False; evaluation decides hits.
        """
        repeats = _repeat_count(n_requests, repeat_ratio)
        unique = n_requests - repeats
        domains = sorted(labels)
        if unique < 1 or unique > len(domains):
            raise ConfigError(
                f"workload needs {unique} distinct domains but {len(domains)} are labeled"
            )
        rng = random.Random(seed)  # noqa: S311 - seeded sampling, not security
        order = rng.sample(domains, unique)
        for _ in range(repeats):
            position = rng.randint(1, len(order))
            order.insert(position, rng.choice(order[:position]))
        return tuple(
            QualificationRequest(
                task_id=f"task-{index:04d}",
                domain=domain,
                split=labels[domain].split,
                data_cache_hit=False,
            )
            for index, domain in enumerate(order, start=1)
        )


def _repeat_count(n_requests: int, repeat_ratio: float) -> int:
    """Return how many requests repeat an earlier domain."""
    if n_requests < 1 or not 0.0 <= repeat_ratio < 1.0:
        raise ConfigError("workload needs n_requests >= 1 and 0 <= repeat_ratio < 1")
    return round(n_requests * repeat_ratio)
