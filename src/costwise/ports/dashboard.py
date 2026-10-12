"""Port for publishing the web dashboard's data file."""

from typing import Protocol


class DashboardSink(Protocol):
    """Stores the dashboard's JSON document."""

    def write(self, body: str) -> str:
        """Store the document, replacing any earlier one, and return where it went."""
        ...
