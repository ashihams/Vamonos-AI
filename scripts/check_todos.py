"""Fail when a verification marker is missing from the ledger."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_MARKER = "TO" + "DO"
SCAN_ROOTS = (Path("src"), Path("tests"), Path("scripts"))
LEDGER = Path("docs/open-verifications.md")
VERIFY_RE = re.compile(_MARKER + r"\(VERIFY: [^)]+\)")
ANY_RE = re.compile(_MARKER + r"\b")


def _python_files() -> list[Path]:
    """Return Python files the marker policy applies to."""
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_dir():
            files.extend(root.rglob("*.py"))
    return sorted(files)


def _ledger_text() -> str:
    """Return the open-verifications ledger."""
    if not LEDGER.is_file():
        return ""
    return LEDGER.read_text(encoding="utf-8")


def _problems_in(path: Path, ledger: str) -> list[str]:
    """Return policy violations found in one file."""
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    for match in ANY_RE.finditer(text):
        line = text[: match.start()].count("\n") + 1
        verified = VERIFY_RE.match(text, match.start())
        if verified is None:
            problems.append(f"{path.as_posix()}:{line}: marker must be {_MARKER}(VERIFY: ...)")
            continue
        token = verified.group(0)
        if token not in ledger:
            problems.append(f"{path.as_posix()}:{line}: {token} missing from {LEDGER.as_posix()}")
    return problems


def main() -> int:
    """Exit non-zero when the marker policy is violated."""
    ledger = _ledger_text()
    problems: list[str] = []
    for path in _python_files():
        problems.extend(_problems_in(path, ledger))
    if problems:
        sys.stderr.write("\n".join(problems) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
