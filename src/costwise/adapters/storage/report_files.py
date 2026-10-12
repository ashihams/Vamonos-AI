"""Write the evidence pack to runs/<run_id>/report/."""

import re
from collections.abc import Mapping
from pathlib import Path

from costwise.adapters.storage.paths import run_directory
from costwise.domain.errors import CostwiseError

_FILE_NAME = re.compile(r"^[a-z0-9_]+\.[a-z]+$")


class FileReportSink:
    """Stores report files in a report folder inside the run directory."""

    def __init__(self, root: Path) -> None:
        """Store reports under root, one directory per run."""
        self._root = root

    def write(self, run_id: str, files: Mapping[str, str]) -> str:
        """Replace each named file and return the report folder."""
        folder = run_directory(self._root, run_id) / "report"
        unsafe = sorted(name for name in files if _FILE_NAME.fullmatch(name) is None)
        if unsafe:
            raise CostwiseError(f"invalid report file names: {', '.join(unsafe)}")
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            (folder / name).write_text(body, encoding="utf-8", newline="\n")
        return folder.as_posix()
