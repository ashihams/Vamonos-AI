"""Port for recording tasks, iterations, and run summaries."""

from typing import Protocol

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class TelemetrySink(Protocol):
    """Accepts run evidence and flushes it before exit."""

    def record_task(self, run_id: str, result: TaskResult) -> None:
        """Record one finished task."""
        ...

    def record_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Record one optimizer iteration."""
        ...

    def record_summary(self, run_id: str, version: int, summary: RunSummary) -> None:
        """Record the aggregate summary for one config version."""
        ...

    def flush(self) -> None:
        """Flush buffered evidence."""
        ...
