"""Baseline runs and the dry-run budget projection."""

from collections.abc import Sequence
from decimal import Decimal

from costwise.domain.config import OptimizerConfig
from costwise.domain.cost import Money
from costwise.domain.errors import ConfigError
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import QualificationRequest, TaskResult
from costwise.ports.storage import ConfigStore
from costwise.ports.telemetry import TelemetrySink
from costwise.services.budget import BudgetService
from costwise.services.evaluation import EvaluationService

MAX_PLAN_SHARE = Decimal("0.5")


class RunReport(FrozenModel):
    """Counts and summed costs for one evaluated set of requests."""

    requested: int
    completed: int
    successes: int
    errors: int
    model_usd: Money
    infra_usd: Money
    data_usd: Money

    @property
    def total_usd(self) -> Decimal:
        """Return model plus infrastructure plus data cost."""
        return self.model_usd + self.infra_usd + self.data_usd


class PlanProjection(FrozenModel):
    """Measured cost per task scaled to the full plan, against the remaining model budget."""

    model_usd_per_task: Money
    total_usd_per_task: Money
    planned_tasks: int
    projected_model_usd: Money
    remaining_budget_usd: Money
    within_budget: bool


def summarize_run(requested: int, results: Sequence[TaskResult]) -> RunReport:
    """Count outcomes and sum cost components."""
    return RunReport(
        requested=requested,
        completed=len(results),
        successes=sum(1 for r in results if r.success),
        errors=sum(1 for r in results if r.invocation.error is not None),
        model_usd=sum((r.costs.model_usd for r in results), Decimal(0)),
        infra_usd=sum((r.costs.infra_usd for r in results), Decimal(0)),
        data_usd=sum((r.costs.data_usd for r in results), Decimal(0)),
    )


def project_plan(report: RunReport, planned_tasks: int, remaining: Decimal) -> PlanProjection:
    """Scale model cost per task to planned_tasks; allow at most half the remaining budget."""
    if report.completed < 1 or planned_tasks < 1:
        raise ConfigError("projection needs at least one completed and one planned task")
    per_task_model = report.model_usd / report.completed
    projected = per_task_model * planned_tasks
    return PlanProjection(
        model_usd_per_task=per_task_model,
        total_usd_per_task=report.total_usd / report.completed,
        planned_tasks=planned_tasks,
        projected_model_usd=projected,
        remaining_budget_usd=remaining,
        within_budget=projected <= remaining * MAX_PLAN_SHARE,
    )


class BaselineService:
    """Evaluate a config, save it with its results, and project the cost of the full plan."""

    def __init__(
        self,
        evaluation: EvaluationService,
        configs: ConfigStore,
        telemetry: TelemetrySink,
        budget: BudgetService,
    ) -> None:
        """Wire evaluation, config storage, telemetry flushing, and the budget."""
        self._evaluation = evaluation
        self._configs = configs
        self._telemetry = telemetry
        self._budget = budget

    def run(
        self, run_id: str, config: OptimizerConfig, requests: Sequence[QualificationRequest]
    ) -> RunReport:
        """Save the config, evaluate the requests, flush telemetry, and report."""
        self._configs.save(run_id, config)
        try:
            results = self._evaluation.evaluate(run_id, config, requests)
        finally:
            self._telemetry.flush()
        return summarize_run(len(requests), results)

    def dry_run(
        self,
        run_id: str,
        config: OptimizerConfig,
        requests: Sequence[QualificationRequest],
        planned_tasks: int,
    ) -> tuple[RunReport, PlanProjection]:
        """Run a small baseline and project its model cost over planned_tasks."""
        report = self.run(run_id, config, requests)
        return report, project_plan(report, planned_tasks, self._budget.remaining())
