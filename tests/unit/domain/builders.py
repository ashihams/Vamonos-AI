"""Builders for domain unit tests."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from costwise.domain.analysis import GroupStats, RunSummary
from costwise.domain.company import CompanyRecord
from costwise.domain.config import OptimizerConfig, RoutingPolicy
from costwise.domain.cost import CostBreakdown, ModelPrice, PriceBook
from costwise.domain.icp import IcpRule
from costwise.domain.task import (
    CallRecord,
    Difficulty,
    InfraCostSource,
    InvocationResult,
    ModelTier,
    QualificationRequest,
    Split,
    TaskResult,
)

_FROZEN = ConfigDict(extra="forbid")


class CallSpec(BaseModel):
    """Overrides for a model call."""

    model_config = _FROZEN

    model: str = "cheap-model"
    tier: ModelTier = ModelTier.CHEAP
    input_tokens: int = 100
    output_tokens: int = 20
    latency_ms: int = 10
    started_offset_ms: int = 0


class ResultSpec(BaseModel):
    """Overrides for one task result."""

    model_config = _FROZEN

    task_id: str = "task-1"
    domain: str = "example.com"
    split: Split = Split.EVAL
    data_cache_hit: bool = False
    difficulty: Difficulty = Difficulty.EASY
    success: bool = True
    model_usd: Decimal = Decimal("0.01")
    infra_usd: Decimal = Decimal("0.001")
    data_usd: Decimal = Decimal("0.002")
    total_latency_ms: int = 100
    calls: tuple[CallRecord, ...] | None = None
    error: str | None = None
    config_version: int = 1
    started_at_ns: int = 1
    infra_source: InfraCostSource = InfraCostSource.MODELED
    billed_ms: int | None = 100
    memory_mb: int | None = 1024
    cold_start: bool = False
    data_credits: Decimal = Decimal("1")


def make_call(spec: CallSpec | None = None) -> CallRecord:
    """Build a call from defaults overridden by spec."""
    chosen = spec or CallSpec()
    return CallRecord(
        model=chosen.model,
        tier=chosen.tier,
        input_tokens=chosen.input_tokens,
        output_tokens=chosen.output_tokens,
        latency_ms=chosen.latency_ms,
        started_offset_ms=chosen.started_offset_ms,
    )


def make_result(spec: ResultSpec | None = None) -> TaskResult:
    """Build a task result from defaults overridden by spec."""
    chosen = spec or ResultSpec()
    calls = (make_call(),) if chosen.calls is None else chosen.calls
    request = QualificationRequest(
        task_id=chosen.task_id,
        domain=chosen.domain,
        split=chosen.split,
        data_cache_hit=chosen.data_cache_hit,
    )
    invocation = InvocationResult(
        task_id=chosen.task_id,
        answer=None,
        calls=calls,
        data_credits=chosen.data_credits,
        total_latency_ms=chosen.total_latency_ms,
        error=chosen.error,
        billed_ms=chosen.billed_ms,
        memory_mb=chosen.memory_mb,
        cold_start=chosen.cold_start,
    )
    costs = CostBreakdown(
        model_usd=chosen.model_usd,
        infra_usd=chosen.infra_usd,
        data_usd=chosen.data_usd,
    )
    return TaskResult(
        request=request,
        config_version=chosen.config_version,
        difficulty=chosen.difficulty,
        invocation=invocation,
        success=chosen.success,
        costs=costs,
        infra_source=chosen.infra_source,
        started_at_ns=chosen.started_at_ns,
    )


def make_prices() -> PriceBook:
    """Return a small price book with exact decimals."""
    return PriceBook(
        models={
            "cheap-model": ModelPrice(
                input_per_1m_usd=Decimal("1"),
                output_per_1m_usd=Decimal("2"),
            ),
            "strong-model": ModelPrice(
                input_per_1m_usd=Decimal("3"),
                output_per_1m_usd=Decimal("4"),
            ),
        },
        lambda_usd_per_gb_second=Decimal("0.0000166667"),
        lambda_usd_per_request=Decimal("0.0000002"),
        crustdata_usd_per_credit=Decimal("0.01"),
    )


def make_rule() -> IcpRule:
    """Return the sample ICP rule used by unit tests."""
    return IcpRule(
        min_employees=50,
        max_employees=1000,
        allowed_stages=frozenset({"series_a", "series_b"}),
        min_engineering_open_roles=10,
        near_threshold_pct=10.0,
    )


def make_company(
    employee_count: int | None,
    funding_stage: str | None,
    engineering_open_roles: int | None,
) -> CompanyRecord:
    """Build a company, leaving the fields the ICP rule ignores empty."""
    return CompanyRecord(
        domain="example.com",
        employee_count=employee_count,
        funding_stage=funding_stage,
        total_funding_usd=None,
        engineering_open_roles=engineering_open_roles,
        industry=None,
        headcount_growth_pct_6m=None,
    )


def make_config() -> OptimizerConfig:
    """Return the unoptimized starting configuration."""
    return OptimizerConfig(
        version=1,
        cheap_model="cheap-model",
        strong_model="strong-model",
        routing=RoutingPolicy(
            default_tier=ModelTier.STRONG,
            strong_if_missing_fields_gte=0,
            strong_if_near_threshold=False,
        ),
        payload_fields=None,
        max_output_tokens=512,
        cache_company_data=False,
        lambda_memory_mb=1024,
    )


def make_summary(success_rate: float, p95_latency_ms: int) -> RunSummary:
    """Build a summary whose guardrail inputs are the two arguments."""
    zero = Decimal(0)
    stats = GroupStats(n=1, successes=1, cost_usd=zero)
    return RunSummary(
        n=1,
        success_rate=success_rate,
        cost_per_successful_task=zero,
        totals=CostBreakdown(model_usd=zero, infra_usd=zero, data_usd=zero),
        by_difficulty={"easy": stats},
        by_tier={"strong": stats},
        p50_latency_ms=p95_latency_ms,
        p95_latency_ms=p95_latency_ms,
        cache_hit_rate=0.0,
        repeat_rate=0.0,
        avg_input_tokens=0.0,
        avg_output_tokens=0.0,
        easy_routed_strong=0,
        hard_routed_cheap_failed=0,
    )
