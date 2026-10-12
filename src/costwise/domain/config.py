"""Optimizer configuration and the levers it can change."""

from enum import StrEnum

from pydantic import Field, field_validator

from costwise.domain.company import COMPANY_FIELD_NAMES
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import ModelTier

MIN_OUTPUT_TOKENS = 64
MAX_OUTPUT_TOKENS = 1024
MIN_MISSING_FIELDS = 0
MAX_MISSING_FIELDS = 5
ALLOWED_MEMORY_MB = frozenset({256, 512, 1024, 2048})


class RoutingPolicy(FrozenModel):
    """Rule for choosing the cheap or strong model."""

    default_tier: ModelTier
    strong_if_missing_fields_gte: int = Field(ge=MIN_MISSING_FIELDS, le=MAX_MISSING_FIELDS)
    strong_if_near_threshold: bool


class OptimizerConfig(FrozenModel):
    """One version of the settings the optimizer is allowed to change."""

    version: int
    cheap_model: str
    strong_model: str
    routing: RoutingPolicy
    payload_fields: tuple[str, ...] | None
    max_output_tokens: int = Field(ge=MIN_OUTPUT_TOKENS, le=MAX_OUTPUT_TOKENS)
    cache_company_data: bool
    lambda_memory_mb: int

    @field_validator("lambda_memory_mb")
    @classmethod
    def _allowed_memory(cls, value: int) -> int:
        """Reject memory sizes outside the allowed Lambda set."""
        if value not in ALLOWED_MEMORY_MB:
            raise ValueError("lambda_memory_mb is not an allowed size")
        return value

    @field_validator("payload_fields")
    @classmethod
    def _known_payload_fields(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Reject payload names that are not company fields."""
        if value is None:
            return None
        unknown = [name for name in value if name not in COMPANY_FIELD_NAMES]
        if unknown:
            message = f"unknown payload fields: {', '.join(unknown)}"
            raise ValueError(message)
        return value


class Lever(StrEnum):
    """The single setting an iteration is allowed to change."""

    ROUTING = "routing"
    PAYLOAD_FIELDS = "payload_fields"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    CACHE = "cache_company_data"
    LAMBDA_MEMORY = "lambda_memory_mb"
