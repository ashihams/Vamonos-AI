"""Telemetry sink that discards everything."""

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class NullSink:
    """Accept and drop telemetry, for runs without an exporter."""

    def record_task(self, run_id: str, result: TaskResult) -> None:
        """Drop one task result."""
        del run_id, result

    def record_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Drop one iteration record."""
        del run_id, record

    def record_summary(self, run_id: str, version: int, summary: RunSummary) -> None:
        """Drop one summary."""
        del run_id, version, summary

    def flush(self) -> None:
        """Do nothing."""
