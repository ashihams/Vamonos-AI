"""Telemetry sink that keeps records in memory."""

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class RecordingTelemetrySink:
    """Append every telemetry call so tests can assert on it."""

    def __init__(self) -> None:
        """Start with empty records and flush not yet called."""
        self.tasks: list[tuple[str, TaskResult]] = []
        self.iterations: list[tuple[str, IterationRecord]] = []
        self.summaries: list[tuple[str, int, RunSummary]] = []
        self.flushed = False

    def record_task(self, run_id: str, result: TaskResult) -> None:
        """Remember one task result."""
        self.tasks.append((run_id, result))

    def record_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Remember one iteration record."""
        self.iterations.append((run_id, record))

    def record_summary(self, run_id: str, version: int, summary: RunSummary) -> None:
        """Remember one run summary."""
        self.summaries.append((run_id, version, summary))

    def flush(self) -> None:
        """Mark that flush was called."""
        self.flushed = True
