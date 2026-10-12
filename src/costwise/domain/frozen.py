"""Shared base for frozen domain models."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Domain model that rejects unknown fields and mutation."""

    model_config = ConfigDict(frozen=True, extra="forbid")
