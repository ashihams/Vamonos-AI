"""Per-version evidence the report files are rendered from."""

from collections.abc import Sequence
from decimal import Decimal

from costwise.domain.analysis import p95_latency_ms
from costwise.domain.cost import CostBreakdown, Money
from costwise.domain.frozen import FrozenModel
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import InfraCostSource, Split, TaskResult

BASELINE = "baseline"
KEPT = "kept"
ROLLED_BACK = "rolled back"


class VersionStats(FrozenModel):
    """Cost, quality, and latency for one evaluated config version."""

    version: int
    status: str
    tasks: int
    eval_tasks: int
    heldout_tasks: int
    successes: int
    totals: CostBreakdown
    cost_per_successful_task: Money | None
    eval_success_rate: float | None
    heldout_success_rate: float | None
    p95_latency_ms: int | None
    infra_sources: tuple[InfraCostSource, ...]


class ReportData(FrozenModel):
    """Everything the report files are rendered from."""

    run_id: str
    baseline: VersionStats
    final: VersionStats
    versions: tuple[VersionStats, ...]
    iterations: tuple[IterationRecord, ...]


def _rate(results: Sequence[TaskResult], split: Split) -> tuple[int, float | None]:
    """Return the task count and success rate for one split, None when it has no tasks."""
    group = [r for r in results if r.request.split is split]
    if not group:
        return 0, None
    return len(group), sum(1 for r in group if r.success) / len(group)


def version_stats(version: int, status: str, results: Sequence[TaskResult]) -> VersionStats:
    """Aggregate one version's results over every task, with success per split."""
    successes = sum(1 for r in results if r.success)
    totals = CostBreakdown(
        model_usd=sum((r.costs.model_usd for r in results), Decimal(0)),
        infra_usd=sum((r.costs.infra_usd for r in results), Decimal(0)),
        data_usd=sum((r.costs.data_usd for r in results), Decimal(0)),
    )
    eval_tasks, eval_rate = _rate(results, Split.EVAL)
    heldout_tasks, heldout_rate = _rate(results, Split.HELDOUT)
    return VersionStats(
        version=version,
        status=status,
        tasks=len(results),
        eval_tasks=eval_tasks,
        heldout_tasks=heldout_tasks,
        successes=successes,
        totals=totals,
        cost_per_successful_task=totals.total_usd / successes if successes else None,
        eval_success_rate=eval_rate,
        heldout_success_rate=heldout_rate,
        p95_latency_ms=p95_latency_ms(results) if results else None,
        infra_sources=tuple(sorted({r.infra_source for r in results})),
    )
