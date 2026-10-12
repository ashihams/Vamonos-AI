"""JSONL files for task results and iteration records."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from costwise.adapters.storage.paths import require_version, run_directory
from costwise.domain.errors import CostwiseError, MissingStoreError
from costwise.domain.frozen import FrozenModel
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult


class JsonlRunStore:
    """Stores results as results_v<n>.jsonl and iterations as iterations.jsonl."""

    def __init__(self, root: Path) -> None:
        """Store artifacts under root, one directory per run."""
        self._root = root

    def save_results(self, run_id: str, version: int, results: Sequence[TaskResult]) -> None:
        """Replace the JSONL results file for this run and version."""
        path = self._results_path(run_id, version)
        _write_models(path, results)

    def load_results(self, run_id: str, version: int) -> list[TaskResult]:
        """Return results previously saved for this run and version."""
        return _read_models(self._results_path(run_id, version), TaskResult)

    def save_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Append one iteration record."""
        path = run_directory(self._root, run_id) / "iterations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")

    def load_iterations(self, run_id: str) -> list[IterationRecord]:
        """Return iteration records in append order."""
        path = run_directory(self._root, run_id) / "iterations.jsonl"
        if not path.is_file():
            return []
        return _read_models(path, IterationRecord)

    def run_ids(self) -> list[str]:
        """Return the names of run directories that hold an iterations file, sorted."""
        if not self._root.is_dir():
            return []
        return sorted(path.parent.name for path in self._root.glob("*/iterations.jsonl"))

    def _results_path(self, run_id: str, version: int) -> Path:
        """Return the results file for a checked version."""
        checked = require_version(version)
        return run_directory(self._root, run_id) / f"results_v{checked}.jsonl"


def _write_models(path: Path, models: Sequence[FrozenModel]) -> None:
    """Write one JSON object per line, replacing the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [model.model_dump_json() for model in models]
    body = "\n".join(lines)
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


def _read_models[ModelT: FrozenModel](path: Path, model: type[ModelT]) -> list[ModelT]:
    """Read JSONL into models, raising CostwiseError when the file is missing or bad."""
    if not path.is_file():
        raise MissingStoreError(f"missing store file: {path.name}")
    loaded: list[ModelT] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded.append(model.model_validate_json(line))
        except ValidationError as exc:
            raise CostwiseError(f"invalid store file: {path.name}") from exc
    return loaded
