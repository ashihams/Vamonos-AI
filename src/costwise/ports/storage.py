"""Ports for persisted task results, iterations, and configs."""

from collections.abc import Sequence
from typing import Protocol

from costwise.domain.config import OptimizerConfig
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class RunStore(Protocol):
    """Persists task results and iteration records for one run."""

    def save_results(self, run_id: str, version: int, results: Sequence[TaskResult]) -> None:
        """Replace the stored results for this run and config version."""
        ...

    def load_results(self, run_id: str, version: int) -> list[TaskResult]:
        """Return the stored results for this run and config version."""
        ...

    def save_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Append one iteration record."""
        ...

    def load_iterations(self, run_id: str) -> list[IterationRecord]:
        """Return iteration records in append order."""
        ...

    def run_ids(self) -> list[str]:
        """Return the ids of runs that have iteration records, sorted."""
        ...


class ConfigStore(Protocol):
    """Persists optimizer configs by run and version."""

    def save(self, run_id: str, config: OptimizerConfig) -> None:
        """Store the config under its version."""
        ...

    def load(self, run_id: str, version: int) -> OptimizerConfig:
        """Return the config for this run and version."""
        ...
