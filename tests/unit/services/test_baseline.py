"""BaselineService, run reports, and the dry-run projection."""

from decimal import Decimal

import pytest

from costwise.domain.errors import ConfigError
from costwise.domain.task import InfraCostSource
from costwise.services.baseline import BaselineService, RunReport, project_plan, summarize_run
from costwise.services.budget import BudgetService
from tests.testing_fakes import FakeRunner, InMemoryConfigStore, RecordingTelemetrySink
from tests.unit.domain.builders import make_config, make_prices
from tests.unit.eval_support import (
    LOCAL_LEVERS,
    answering_runner,
    domain,
    make_evaluation,
    make_labels,
    make_requests,
)


def _report(completed: int, model_usd: str) -> RunReport:
    """Build a report with only model cost."""
    zero = Decimal(0)
    return RunReport(
        requested=completed,
        completed=completed,
        successes=completed,
        errors=0,
        model_usd=Decimal(model_usd),
        infra_usd=zero,
        data_usd=Decimal("0.5"),
    )


def _baseline(
    runner: FakeRunner, cap: str = "10"
) -> tuple[BaselineService, InMemoryConfigStore, RecordingTelemetrySink]:
    """Wire a baseline service over fakes and a real budget."""
    labels = make_labels(4)
    harness = make_evaluation(runner, labels)
    configs = InMemoryConfigStore()
    budget = BudgetService(Decimal(cap), 0.8, make_prices())
    return (
        BaselineService(harness.service, configs, harness.telemetry, budget),
        configs,
        harness.telemetry,
    )


def test_run_saves_config_evaluates_flushes_and_reports() -> None:
    """The config is stored, telemetry is flushed, and the report sums outcomes and costs."""
    labels = make_labels(4)
    service, configs, telemetry = _baseline(answering_runner(labels, wrong={domain(1)}))
    report = service.run("run-1", make_config(), make_requests(0, 1, 2))
    assert configs.load("run-1", 1) == make_config()
    assert telemetry.flushed
    assert (report.requested, report.completed, report.successes, report.errors) == (3, 3, 2, 0)
    assert report.model_usd == Decimal("0.0102")
    assert report.data_usd == Decimal("0.06")
    assert report.total_usd == Decimal("0.0702")


def test_run_records_the_eval_summary_only_when_something_succeeded() -> None:
    """A summary of the EVAL results goes to telemetry; an all-failed run sends none."""
    labels = make_labels(4)
    service, _, telemetry = _baseline(answering_runner(labels, wrong={domain(1)}))
    service.run("run-1", make_config(), make_requests(0, 1))
    assert [(run, version, summary.n) for run, version, summary in telemetry.summaries] == [
        ("run-1", 1, 2)
    ]

    all_wrong = {domain(i) for i in range(4)}
    failing, _, quiet = _baseline(answering_runner(labels, wrong=all_wrong))
    failing.run("run-2", make_config(), make_requests(0, 1))
    assert quiet.summaries == []


def test_run_flushes_telemetry_even_when_evaluation_fails() -> None:
    """An evaluation that raises still flushes what was recorded."""
    service, _, telemetry = _baseline(FakeRunner(LOCAL_LEVERS, InfraCostSource.MODELED, []))
    with pytest.raises(ConfigError, match="no label for"):
        service.run("run-1", make_config(), make_requests(99))
    assert telemetry.flushed


def test_projection_scales_model_cost_and_compares_with_half_the_budget() -> None:
    """Per-task model cost times planned tasks must be at most half of what remains."""
    fits = project_plan(_report(5, "0.05"), planned_tasks=160, remaining=Decimal("4"))
    assert fits.model_usd_per_task == Decimal("0.01")
    assert fits.total_usd_per_task == Decimal("0.11")
    assert fits.projected_model_usd == Decimal("1.60")
    assert fits.within_budget
    over = project_plan(_report(5, "0.05"), planned_tasks=160, remaining=Decimal("3"))
    assert not over.within_budget
    with pytest.raises(ConfigError, match="projection needs"):
        project_plan(_report(0, "0"), planned_tasks=160, remaining=Decimal("3"))


def test_dry_run_projects_against_remaining_budget_after_the_run() -> None:
    """Dry run reports the small run and projects it over the planned tasks."""
    labels = make_labels(4)
    service, _, _ = _baseline(answering_runner(labels))
    report, projection = service.dry_run(
        "dry", make_config(), make_requests(0, 1), planned_tasks=100
    )
    assert report.completed == 2
    assert projection.projected_model_usd == Decimal("0.3400")
    assert projection.remaining_budget_usd == Decimal("10")
    assert projection.within_budget


def test_summarize_counts_errors() -> None:
    """Results with an invocation error are counted."""
    labels = make_labels(1)
    harness = make_evaluation(answering_runner(labels), labels)
    result = harness.service.evaluate("r", make_config(), make_requests(0))[0]
    failed = result.model_copy(
        update={"invocation": result.invocation.model_copy(update={"error": "LLMError: x"})}
    )
    assert summarize_run(2, [failed]).errors == 1
