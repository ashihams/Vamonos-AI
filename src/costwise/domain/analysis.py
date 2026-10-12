"""Run summaries computed from task results."""

from collections.abc import Sequence
from decimal import Decimal

from costwise.domain.cost import CostBreakdown, Money
from costwise.domain.errors import CostwiseError
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import Difficulty, ModelTier, TaskResult

_P50 = 50
_P95 = 95
_CEIL_BIAS = 99
_PERCENT_SCALE = 100


class GroupStats(FrozenModel):
    """Count, successes, and cost for one slice of a run."""

    n: int
    successes: int
    cost_usd: Money


class RunSummary(FrozenModel):
    """Aggregate quality, cost, latency, and routing for one split."""

    n: int
    success_rate: float
    cost_per_successful_task: Money
    totals: CostBreakdown
    by_difficulty: dict[str, GroupStats]
    by_tier: dict[str, GroupStats]
    p50_latency_ms: int
    p95_latency_ms: int
    cache_hit_rate: float
    repeat_rate: float
    avg_input_tokens: float
    avg_output_tokens: float
    easy_routed_strong: int
    hard_routed_cheap_failed: int


def summarize(results: Sequence[TaskResult]) -> RunSummary:
    """Aggregate task results. Raise if none of them succeeded.

    Token averages are the mean, over tasks, of the sum of tokens across that
    task's calls. Latency percentiles use the nearest-rank method.
    ``success_rate``, ``cache_hit_rate``, and ``repeat_rate`` are fractions from 0 to 1.
    ``repeat_rate`` is the share of tasks whose domain appeared earlier in ``results``,
    which is the hit rate a company-data cache could reach.
    """
    successes = sum(1 for result in results if result.success)
    if not successes:
        raise CostwiseError("no successful tasks")
    totals = _totals(results)
    count = len(results)
    latencies = [result.invocation.total_latency_ms for result in results]
    easy_strong, hard_cheap_failed = _routed_counts(results)
    hits = sum(1 for result in results if result.request.data_cache_hit)
    return RunSummary(
        n=count,
        success_rate=successes / count,
        cost_per_successful_task=totals.total_usd / Decimal(successes),
        totals=totals,
        by_difficulty=_by_difficulty(results),
        by_tier=_by_tier(results),
        p50_latency_ms=_nearest_rank(latencies, _P50),
        p95_latency_ms=_nearest_rank(latencies, _P95),
        cache_hit_rate=hits / count,
        repeat_rate=_repeats(results) / count,
        avg_input_tokens=_avg_input_tokens(results),
        avg_output_tokens=_avg_output_tokens(results),
        easy_routed_strong=easy_strong,
        hard_routed_cheap_failed=hard_cheap_failed,
    )


def _totals(results: Sequence[TaskResult]) -> CostBreakdown:
    """Sum component costs across tasks."""
    model = Decimal(0)
    infra = Decimal(0)
    data = Decimal(0)
    for result in results:
        model += result.costs.model_usd
        infra += result.costs.infra_usd
        data += result.costs.data_usd
    return CostBreakdown(model_usd=model, infra_usd=infra, data_usd=data)


def _by_difficulty(results: Sequence[TaskResult]) -> dict[str, GroupStats]:
    """Group tasks into easy and hard slices."""
    groups: dict[str, list[TaskResult]] = {
        Difficulty.EASY.value: [],
        Difficulty.HARD.value: [],
    }
    for result in results:
        groups[result.difficulty.value].append(result)
    return {key: _stats(group) for key, group in groups.items()}


def _by_tier(results: Sequence[TaskResult]) -> dict[str, GroupStats]:
    """Group tasks by the tier of their first model call."""
    groups: dict[str, list[TaskResult]] = {}
    for result in results:
        tier = _first_tier(result)
        if tier is None:
            continue
        groups.setdefault(tier.value, []).append(result)
    return {key: _stats(group) for key, group in groups.items()}


def _stats(group: Sequence[TaskResult]) -> GroupStats:
    """Summarize one group of tasks."""
    cost = Decimal(0)
    successes = 0
    for result in group:
        cost += result.costs.total_usd
        if result.success:
            successes += 1
    return GroupStats(n=len(group), successes=successes, cost_usd=cost)


def _routed_counts(results: Sequence[TaskResult]) -> tuple[int, int]:
    """Return easy-to-strong and failed hard-to-cheap counts."""
    easy_strong = 0
    hard_cheap_failed = 0
    for result in results:
        tier = _first_tier(result)
        if result.difficulty is Difficulty.EASY and tier is ModelTier.STRONG:
            easy_strong += 1
        if result.difficulty is Difficulty.HARD and tier is ModelTier.CHEAP and not result.success:
            hard_cheap_failed += 1
    return easy_strong, hard_cheap_failed


def _first_tier(result: TaskResult) -> ModelTier | None:
    """Return the tier of the first call, if the task made one."""
    if not result.invocation.calls:
        return None
    return result.invocation.calls[0].tier


def _repeats(results: Sequence[TaskResult]) -> int:
    """Count tasks whose domain appeared earlier in the sequence."""
    seen: set[str] = set()
    repeats = 0
    for result in results:
        domain = result.request.domain
        repeats += domain in seen
        seen.add(domain)
    return repeats


def _avg_input_tokens(results: Sequence[TaskResult]) -> float:
    """Return mean input tokens per task, summing every call on the task."""
    total = sum(call.input_tokens for result in results for call in result.invocation.calls)
    return total / len(results)


def _avg_output_tokens(results: Sequence[TaskResult]) -> float:
    """Return mean output tokens per task, summing every call on the task."""
    total = sum(call.output_tokens for result in results for call in result.invocation.calls)
    return total / len(results)


def _nearest_rank(values: Sequence[int], percent: int) -> int:
    """Return the nearest-rank percentile. ``values`` must be non-empty."""
    ordered = sorted(values)
    rank = (percent * len(ordered) + _CEIL_BIAS) // _PERCENT_SCALE
    return ordered[rank - 1]
