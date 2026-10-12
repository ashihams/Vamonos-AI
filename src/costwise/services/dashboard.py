"""Flatten stored runs into one JSON document for the web dashboard."""

from collections.abc import Sequence

from costwise.domain.cost import CostBreakdown
from costwise.domain.errors import CostwiseError
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import CallRecord, Difficulty, InfraCostSource, Split, TaskResult
from costwise.ports.dashboard import DashboardSink
from costwise.ports.storage import RunStore
from costwise.services.report import collect_report
from costwise.services.report_data import ReportData


class DashboardTask(FrozenModel):
    """One task as the dashboard's task explorer shows it."""

    version: int
    task_id: str
    domain: str
    split: Split
    difficulty: Difficulty
    success: bool
    cache_hit: bool
    icp_fit: bool | None
    reasons: tuple[str, ...]
    error: str | None
    latency_ms: int
    costs: CostBreakdown
    infra_source: InfraCostSource
    calls: tuple[CallRecord, ...]


class DashboardRun(FrozenModel):
    """Per-version stats, iterations, and every task of one run."""

    report: ReportData
    tasks: tuple[DashboardTask, ...]


class DashboardData(FrozenModel):
    """Every exported run."""

    runs: tuple[DashboardRun, ...]


class DashboardExport(FrozenModel):
    """Where the document went and what it holds."""

    location: str
    runs: int
    tasks: int


def dashboard_task(result: TaskResult) -> DashboardTask:
    """Return the explorer row for one task result."""
    answer = result.invocation.answer
    return DashboardTask(
        version=result.config_version,
        task_id=result.request.task_id,
        domain=result.request.domain,
        split=result.request.split,
        difficulty=result.difficulty,
        success=result.success,
        cache_hit=result.request.data_cache_hit,
        icp_fit=None if answer is None else answer.icp_fit,
        reasons=() if answer is None else answer.reasons,
        error=result.invocation.error,
        latency_ms=result.invocation.total_latency_ms,
        costs=result.costs,
        infra_source=result.infra_source,
        calls=result.invocation.calls,
    )


class DashboardService:
    """Read stored runs and publish them as one dashboard document."""

    def __init__(self, runs: RunStore, sink: DashboardSink) -> None:
        """Read from runs and write through sink."""
        self._runs = runs
        self._sink = sink

    def collect(self, run_ids: Sequence[str]) -> DashboardData:
        """Return the named runs, or every run with iterations when none are named."""
        chosen = list(run_ids) or self._runs.run_ids()
        if not chosen:
            raise CostwiseError("no runs with iterations to export")
        return DashboardData(runs=tuple(self._run(run_id) for run_id in chosen))

    def export(self, run_ids: Sequence[str]) -> DashboardExport:
        """Write the document and return where it went with its run and task counts."""
        data = self.collect(run_ids)
        location = self._sink.write(data.model_dump_json(indent=1))
        tasks = sum(len(run.tasks) for run in data.runs)
        return DashboardExport(location=location, runs=len(data.runs), tasks=tasks)

    def _run(self, run_id: str) -> DashboardRun:
        """Collect one run's report data and the tasks of each version it evaluated."""
        report = collect_report(self._runs, run_id)
        tasks: list[DashboardTask] = []
        for stats in report.versions:
            results = self._runs.load_results(run_id, stats.version)
            tasks.extend(dashboard_task(result) for result in results)
        return DashboardRun(report=report, tasks=tuple(tasks))
