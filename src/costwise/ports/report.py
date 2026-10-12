"""Port for storing the evidence pack."""

from collections.abc import Mapping
from typing import Protocol


class ReportSink(Protocol):
    """Stores named report files for one run."""

    def write(self, run_id: str, files: Mapping[str, str]) -> str:
        """Store each file under its name and return where they went."""
        ...
