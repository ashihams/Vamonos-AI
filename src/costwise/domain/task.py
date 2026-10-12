"""Task requests, model calls, and runner results."""

from enum import StrEnum

from costwise.domain.cost import CostBreakdown, Money
from costwise.domain.frozen import FrozenModel


class Difficulty(StrEnum):
    """How hard a company is to qualify against the ICP rule."""

    EASY = "easy"
    HARD = "hard"


class Split(StrEnum):
    """Whether a task may be shown to the optimizer."""

    EVAL = "eval"
    HELDOUT = "heldout"


class ModelTier(StrEnum):
    """Which model tier handled a call."""

    CHEAP = "cheap"
    STRONG = "strong"


class InfraCostSource(StrEnum):
    """Whether infrastructure cost was measured or modeled."""

    MEASURED = "measured"
    MODELED = "modeled"


class QualificationRequest(FrozenModel):
    """One company-qualification task handed to a runner."""

    task_id: str
    domain: str
    split: Split
    data_cache_hit: bool


class QualificationAnswer(FrozenModel):
    """Structured qualification the model must return."""

    icp_fit: bool
    reasons: tuple[str, ...]
    headcount_band: str | None
    stage: str | None


class CallRecord(FrozenModel):
    """One model call made while qualifying a company."""

    model: str
    tier: ModelTier
    input_tokens: int
    output_tokens: int
    latency_ms: int
    started_offset_ms: int


class InvocationResult(FrozenModel):
    """Serializable result a runner returns for one task."""

    task_id: str
    answer: QualificationAnswer | None
    calls: tuple[CallRecord, ...]
    data_credits: Money
    total_latency_ms: int
    error: str | None
    billed_ms: int | None
    memory_mb: int | None
    cold_start: bool


class TaskResult(FrozenModel):
    """Invocation plus ground truth, success, and cost."""

    request: QualificationRequest
    config_version: int
    difficulty: Difficulty
    invocation: InvocationResult
    success: bool
    costs: CostBreakdown
    infra_source: InfraCostSource
    started_at_ns: int
