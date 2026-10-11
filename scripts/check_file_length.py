"""Fail when a Python file under src/ exceeds the line limit."""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 250
SRC_ROOT = Path("src")


def _python_files(root: Path) -> list[Path]:
    """Return Python files under root, in stable order."""
    return sorted(root.rglob("*.py"))


def _line_count(path: Path) -> int:
    """Return the number of lines in path."""
    return len(path.read_text(encoding="utf-8").splitlines())


def main() -> int:
    """Exit non-zero when any source file is too long."""
    if not SRC_ROOT.is_dir():
        sys.stderr.write(f"missing {SRC_ROOT}\n")
        return 1
    failures = [
        f"{path.as_posix()}: {_line_count(path)} lines (max {MAX_LINES})"
        for path in _python_files(SRC_ROOT)
        if _line_count(path) > MAX_LINES
    ]
    if failures:
        sys.stderr.write("\n".join(failures) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
