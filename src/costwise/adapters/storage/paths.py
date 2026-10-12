"""Safe relative paths for run artifacts."""

import re
from pathlib import Path

from costwise.domain.errors import CostwiseError

_MIN_VERSION = 0
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def run_directory(root: Path, run_id: str) -> Path:
    """Return the directory for a run id that cannot escape root."""
    if _RUN_ID.fullmatch(run_id) is None:
        raise CostwiseError("invalid run id")
    return root / run_id


def require_version(version: int) -> int:
    """Return version when it is zero or positive."""
    if version < _MIN_VERSION:
        raise CostwiseError("invalid config version")
    return version
