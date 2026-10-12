"""Write the dashboard's JSON document to one file."""

from pathlib import Path


class FileDashboardSink:
    """Stores the dashboard document at a fixed path."""

    def __init__(self, path: Path) -> None:
        """Write to path, creating its folder when needed."""
        self._path = path

    def write(self, body: str) -> str:
        """Replace the file and return its path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(body, encoding="utf-8", newline="\n")
        return self._path.as_posix()
