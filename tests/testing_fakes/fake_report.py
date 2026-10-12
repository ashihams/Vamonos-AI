"""A report sink that keeps written files in memory."""

from collections.abc import Mapping


class RecordingReportSink:
    """Remember every report written, keyed by run id."""

    def __init__(self) -> None:
        """Start with no reports."""
        self.reports: dict[str, dict[str, str]] = {}

    def write(self, run_id: str, files: Mapping[str, str]) -> str:
        """Keep a copy of the files and return a fake location."""
        self.reports[run_id] = dict(files)
        return f"memory://{run_id}/report"
