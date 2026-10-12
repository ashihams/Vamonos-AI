"""In-memory run and config stores."""

from collections.abc import Sequence

from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import MissingStoreError
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class InMemoryRunStore:
    """Keep results and iterations in dictionaries."""

    def __init__(self) -> None:
        """Start with no saved runs."""
        self._results: dict[tuple[str, int], list[TaskResult]] = {}
        self._iterations: dict[str, list[IterationRecord]] = {}

    def save_results(self, run_id: str, version: int, results: Sequence[TaskResult]) -> None:
        """Replace the stored results for this run and version."""
        self._results[(run_id, version)] = list(results)

    def load_results(self, run_id: str, version: int) -> list[TaskResult]:
        """Return a copy of the stored results."""
        try:
            saved = self._results[(run_id, version)]
        except KeyError as exc:
            raise MissingStoreError("missing store file: results") from exc
        return list(saved)

    def save_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Append one iteration record."""
        self._iterations.setdefault(run_id, []).append(record)

    def load_iterations(self, run_id: str) -> list[IterationRecord]:
        """Return a copy of the iteration records in append order."""
        return list(self._iterations.get(run_id, []))


class InMemoryConfigStore:
    """Keep optimizer configs in a dictionary."""

    def __init__(self) -> None:
        """Start with no saved configs."""
        self._configs: dict[tuple[str, int], OptimizerConfig] = {}

    def save(self, run_id: str, config: OptimizerConfig) -> None:
        """Store the config under its version."""
        self._configs[(run_id, config.version)] = config

    def load(self, run_id: str, version: int) -> OptimizerConfig:
        """Return the config for this run and version."""
        try:
            return self._configs[(run_id, version)]
        except KeyError as exc:
            raise MissingStoreError("missing store file: config") from exc
