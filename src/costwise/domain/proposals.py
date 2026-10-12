"""Proposals that change exactly one optimizer lever."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, SkipValidation, ValidationError

from costwise.domain.analysis import RunSummary
from costwise.domain.company import COMPANY_FIELD_NAMES
from costwise.domain.config import (
    ALLOWED_MEMORY_MB,
    MAX_OUTPUT_TOKENS,
    MIN_OUTPUT_TOKENS,
    Lever,
    OptimizerConfig,
    RoutingPolicy,
)
from costwise.domain.errors import ConfigError
from costwise.domain.frozen import FrozenModel
from costwise.domain.guardrails import GuardrailResult

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


def _as_json(value: object) -> JsonValue:
    """Keep JSON types as written, without coercing integers or strings into booleans."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, list):
        return [_as_json(item) for item in value]
    if isinstance(value, dict):
        return _json_object(value)
    raise ValueError("value is not JSON")


def _json_object(value: dict[object, object]) -> dict[str, JsonValue]:
    """Parse a JSON object, requiring string keys."""
    parsed: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("JSON object keys must be strings")
        parsed[key] = _as_json(item)
    return parsed


class Proposal(FrozenModel):
    """One suggested lever change, with the predicted effect and risk."""

    lever: Lever
    new_value: Annotated[JsonValue, SkipValidation(), BeforeValidator(_as_json)]
    rationale: str
    predicted_cost_change_pct: float
    risk: Literal["low", "medium", "high"]


class ApprovalDecision(FrozenModel):
    """A human or automatic decision on one proposal."""

    approved: bool
    note: str


class IterationRecord(FrozenModel):
    """What happened in one propose, approve, and verify cycle."""

    iteration: int
    proposal: Proposal
    decision: ApprovalDecision
    baseline_version: int
    candidate_version: int | None
    candidate_summary: RunSummary | None
    guardrails: GuardrailResult | None
    accepted: bool
    reason: str


def validate_proposal(
    proposal: Proposal,
    current: OptimizerConfig,
    available: frozenset[Lever],
) -> None:
    """Raise ConfigError when the lever, value, or change is not allowed."""
    if proposal.lever not in available:
        raise ConfigError("lever is not available")
    _parsed_value(proposal)
    if _same_as_current(proposal, current):
        raise ConfigError("no actual change")


def apply_proposal(current: OptimizerConfig, proposal: Proposal) -> OptimizerConfig:
    """Return a new config with this lever changed and the version incremented."""
    changed = _with_lever(current, proposal)
    return changed.model_copy(update={"version": current.version + 1})


def _parsed_value(proposal: Proposal) -> RoutingPolicy | tuple[str, ...] | int | bool | None:
    """Return the typed lever value, or raise ConfigError when it is out of bounds."""
    if proposal.lever is Lever.ROUTING:
        return _routing_from_json(proposal.new_value)
    if proposal.lever is Lever.PAYLOAD_FIELDS:
        return _payload_from_json(proposal.new_value)
    if proposal.lever is Lever.CACHE:
        return _require_bool(proposal.new_value)
    if proposal.lever is Lever.MAX_OUTPUT_TOKENS:
        return _bounded_int(proposal.new_value, MIN_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS)
    return _memory(proposal.new_value)


def _same_as_current(proposal: Proposal, current: OptimizerConfig) -> bool:
    """Return whether the proposal leaves the current lever value unchanged."""
    if proposal.lever is Lever.ROUTING:
        return _routing_from_json(proposal.new_value) == current.routing
    if proposal.lever is Lever.PAYLOAD_FIELDS:
        return _payload_from_json(proposal.new_value) == current.payload_fields
    if proposal.lever is Lever.CACHE:
        return _require_bool(proposal.new_value) is current.cache_company_data
    if proposal.lever is Lever.MAX_OUTPUT_TOKENS:
        return _bounded_int(proposal.new_value, MIN_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS) == (
            current.max_output_tokens
        )
    return _memory(proposal.new_value) == current.lambda_memory_mb


def _with_lever(current: OptimizerConfig, proposal: Proposal) -> OptimizerConfig:
    """Copy current with the proposal's lever replaced."""
    if proposal.lever is Lever.ROUTING:
        return current.model_copy(update={"routing": _routing_from_json(proposal.new_value)})
    if proposal.lever is Lever.PAYLOAD_FIELDS:
        return current.model_copy(update={"payload_fields": _payload_from_json(proposal.new_value)})
    if proposal.lever is Lever.CACHE:
        return current.model_copy(update={"cache_company_data": _require_bool(proposal.new_value)})
    if proposal.lever is Lever.MAX_OUTPUT_TOKENS:
        tokens = _bounded_int(proposal.new_value, MIN_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS)
        return current.model_copy(update={"max_output_tokens": tokens})
    return current.model_copy(update={"lambda_memory_mb": _memory(proposal.new_value)})


def _routing_from_json(value: JsonValue) -> RoutingPolicy:
    """Parse a routing object into a policy."""
    if not isinstance(value, dict):
        raise ConfigError("routing value must be an object")
    missing = value.get("strong_if_missing_fields_gte")
    if isinstance(missing, bool):
        raise ConfigError("strong_if_missing_fields_gte must be an integer")
    try:
        return RoutingPolicy.model_validate(value)
    except ValidationError as exc:
        raise ConfigError("routing value is invalid") from exc


def _payload_from_json(value: JsonValue) -> tuple[str, ...] | None:
    """Parse null or a list of company field names."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ConfigError("payload_fields must be a list of field names or null")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError("payload_fields must be a list of field names or null")
        names.append(item)
    unknown = [name for name in names if name not in COMPANY_FIELD_NAMES]
    if unknown:
        raise ConfigError(f"unknown payload fields: {', '.join(unknown)}")
    if len(names) != len(set(names)):
        raise ConfigError("payload_fields contains duplicates")
    return tuple(names)


def _require_bool(value: JsonValue) -> bool:
    """Return value when it is a boolean."""
    if not isinstance(value, bool):
        raise ConfigError("expected a boolean")
    return value


def _require_int(value: JsonValue) -> int:
    """Return value when it is an integer and not a boolean."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("expected an integer")
    return value


def _bounded_int(value: JsonValue, low: int, high: int) -> int:
    """Return an integer inside the inclusive bounds."""
    number = _require_int(value)
    if number < low or number > high:
        raise ConfigError(f"value must be between {low} and {high}")
    return number


def _memory(value: JsonValue) -> int:
    """Return a Lambda memory size from the allowed set."""
    number = _require_int(value)
    if number not in ALLOWED_MEMORY_MB:
        raise ConfigError("lambda_memory_mb is not an allowed size")
    return number
