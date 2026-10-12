"""JSON files for optimizer configs."""

from pathlib import Path

from pydantic import ValidationError

from costwise.adapters.storage.paths import require_version, run_directory
from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import CostwiseError


class FileConfigStore:
    """Stores each config version as config_v<n>.json."""

    def __init__(self, root: Path) -> None:
        """Store configs under root, one directory per run."""
        self._root = root

    def save(self, run_id: str, config: OptimizerConfig) -> None:
        """Write the config JSON for its version."""
        path = self._path(run_id, config.version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config.model_dump_json(), encoding="utf-8")

    def load(self, run_id: str, version: int) -> OptimizerConfig:
        """Return the config saved for this run and version."""
        path = self._path(run_id, version)
        if not path.is_file():
            raise CostwiseError(f"missing store file: {path.name}")
        try:
            return OptimizerConfig.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise CostwiseError(f"invalid store file: {path.name}") from exc

    def _path(self, run_id: str, version: int) -> Path:
        """Return the config file for a checked version."""
        checked = require_version(version)
        return run_directory(self._root, run_id) / f"config_v{checked}.json"
