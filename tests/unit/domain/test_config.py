"""Optimizer config bounds."""

import pytest
from pydantic import ValidationError

from costwise.domain.config import OptimizerConfig, RoutingPolicy
from costwise.domain.task import ModelTier
from tests.unit.domain.builders import make_config


def _validated(**changes: object) -> OptimizerConfig:
    """Rebuild a config through validation so field bounds run."""
    raw = make_config().model_dump()
    raw.update(changes)
    return OptimizerConfig.model_validate(raw)


def test_config_rejects_memory_outside_the_lambda_set() -> None:
    """Memory must be one of the four allowed sizes."""
    with pytest.raises(ValidationError):
        _validated(lambda_memory_mb=128)


def test_config_rejects_output_cap_outside_bounds() -> None:
    """The output cap stays inside 64 to 1024."""
    with pytest.raises(ValidationError):
        _validated(max_output_tokens=32)


def test_config_rejects_unknown_payload_fields() -> None:
    """Payload names have to be company fields."""
    with pytest.raises(ValidationError):
        _validated(payload_fields=["hiring"])


def test_config_accepts_known_payload_fields() -> None:
    """A tuple of real company fields is stored unchanged."""
    updated = _validated(payload_fields=["employee_count", "domain"])
    assert updated.payload_fields == ("employee_count", "domain")


@pytest.mark.parametrize("missing", [-1, 6])
def test_routing_rejects_missing_field_threshold_outside_bounds(missing: int) -> None:
    """The missing-field threshold stays inside 0 to 5."""
    with pytest.raises(ValidationError):
        RoutingPolicy(
            default_tier=ModelTier.CHEAP,
            strong_if_missing_fields_gte=missing,
            strong_if_near_threshold=False,
        )


def test_config_model_is_frozen() -> None:
    """Configs are replaced rather than mutated."""
    config = make_config()
    with pytest.raises(ValidationError):
        config.version = 2  # type: ignore[misc]
    assert isinstance(config, OptimizerConfig)
