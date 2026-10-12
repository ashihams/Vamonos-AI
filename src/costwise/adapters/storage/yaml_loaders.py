"""Load price, ICP, policy, and workload YAML into domain models."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from costwise.domain.config import OptimizerConfig
from costwise.domain.cost import PriceBook
from costwise.domain.errors import ConfigError
from costwise.domain.frozen import FrozenModel
from costwise.domain.guardrails import GuardrailPolicy
from costwise.domain.icp import IcpRule
from costwise.domain.labels import WorkloadPolicy


def load_price_book(path: Path) -> PriceBook:
    """Load a price book, raising ConfigError with the file name and field."""
    return _validate(path, PriceBook, _mapping(path))


def load_icp_rule(path: Path) -> IcpRule:
    """Load an ICP rule, raising ConfigError with the file name and field."""
    return _validate(path, IcpRule, _mapping(path))


def load_guardrail_policy(path: Path) -> GuardrailPolicy:
    """Load the guardrails section of a policy file."""
    return _validate(path, GuardrailPolicy, _section(path, "guardrails"))


def load_initial_config(path: Path) -> OptimizerConfig:
    """Load the initial_config section of a policy file."""
    return _validate(path, OptimizerConfig, _section(path, "initial_config"))


def load_workload_policy(path: Path) -> WorkloadPolicy:
    """Load the workload section of a policy file."""
    return _validate(path, WorkloadPolicy, _section(path, "workload"))


def _mapping(path: Path) -> dict[str, object]:
    """Return the YAML document when it is a mapping."""
    loaded = _read_yaml(path)
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path.name}: document")
    return {str(key): item for key, item in loaded.items()}


def _read_yaml(path: Path) -> object:
    """Read YAML text into a Python object."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{path.name}: unreadable") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: invalid YAML") from exc


def _section(path: Path, field: str) -> object:
    """Return one mapping section or raise ConfigError for a missing field."""
    document = _mapping(path)
    if field not in document:
        raise ConfigError(f"{path.name}: {field}")
    return document[field]


def _validate[ModelT: FrozenModel](path: Path, model: type[ModelT], raw: object) -> ModelT:
    """Validate raw data and include the file name and field in failures."""
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: {_field_name(exc)}") from exc


def _field_name(exc: ValidationError) -> str:
    """Return the first invalid field path, or document when it has no location."""
    loc = exc.errors()[0]["loc"]
    if not loc:
        return "document"
    return ".".join(str(part) for part in loc)
