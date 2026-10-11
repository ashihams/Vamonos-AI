"""Remove local build and test caches."""

from __future__ import annotations

import shutil
from pathlib import Path

_DIRS = (
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "htmlcov",
    "build",
    "dist",
)
_FILES = (".coverage",)
_TREE_ROOTS = (Path("src"), Path("tests"), Path("scripts"))


def _remove_caches() -> None:
    """Delete generated directories, coverage data, and bytecode caches."""
    for name in _DIRS:
        shutil.rmtree(name, ignore_errors=True)
    for name in _FILES:
        Path(name).unlink(missing_ok=True)
    for root in _TREE_ROOTS:
        for cache in root.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    for egg in Path("src").glob("*.egg-info"):
        shutil.rmtree(egg, ignore_errors=True)


def main() -> int:
    """Exit after caches are removed."""
    _remove_caches()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
