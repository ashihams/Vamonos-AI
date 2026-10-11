"""CLI commands with fake dependencies supplied through the Typer context."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from costwise.apps.cli import main as cli_main
from costwise.apps.cli.main import app
from costwise.bootstrap import CliDeps, EvalStack, FixtureStack, RunnerKind
from costwise.domain.errors import ConfigError
from costwise.domain.labels import WorkloadPolicy
from costwise.ports.data import CompanyDataSource, CompanyFetch
from costwise.services.baseline import BaselineService
from costwise.services.budget import BudgetService
from costwise.services.fixtures import FixtureService
from tests.testing_fakes import FakeCompanySource, InMemoryConfigStore, InMemoryFixtureStore
from tests.unit.domain.builders import make_company, make_config, make_prices, make_rule
from tests.unit.eval_support import answering_runner, make_evaluation, make_labels, make_requests

_RUNNER = CliRunner()


def _eval_stack(cap: str) -> EvalStack:
    """Wire a baseline over four labeled companies and a real budget with the given cap."""
    labels = make_labels(4)
    runner = answering_runner(labels)
    harness = make_evaluation(runner, labels)
    budget = BudgetService(Decimal(cap), 0.8, make_prices())
    baseline = BaselineService(harness.service, InMemoryConfigStore(), harness.telemetry, budget)
    return EvalStack(
        baseline, make_config(), tuple(make_requests(0, 1, 2, 3)), runner.capabilities()
    )


def _fetch(domain: str, employees: int, stage: str | None, roles: int | None) -> CompanyFetch:
    """Build a fetch for one company."""
    record = make_company(employees, stage, roles).model_copy(update={"domain": domain})
    return CompanyFetch(record=record, raw={}, credits_used=Decimal(2))


def _deps(
    cap: str = "10",
    store: InMemoryFixtureStore | None = None,
    eval_stack: Callable[[RunnerKind], AbstractContextManager[EvalStack]] | None = None,
) -> CliDeps:
    """Return CLI dependencies backed by fakes."""
    fixtures = store or InMemoryFixtureStore()
    workload = WorkloadPolicy(n_requests=4, repeat_ratio=0.0, heldout_count=2, seed=7)
    source: CompanyDataSource = FakeCompanySource(
        {"a.example.com": _fetch("a.example.com", 300, "series_a", 20)}
    )
    return CliDeps(
        eval_stack=eval_stack or (lambda kind: nullcontext(_eval_stack(cap))),
        fixture_stack=lambda fixtures_dir, config_dir: FixtureStack(
            FixtureService(fixtures), make_rule(), workload
        ),
        crustdata_source=lambda: nullcontext(source),
    )


def test_eval_baseline_prints_counts_costs_and_the_modeled_infra_note() -> None:
    """The baseline runs the first N requests and reports them."""
    result = _RUNNER.invoke(
        app, ["eval", "baseline", "--run-id", "r1", "--tasks", "2"], obj=_deps()
    )
    assert result.exit_code == 0, result.output
    assert "tasks: 2 of 2 completed, 0 with errors" in result.output
    assert "success: 2 (100.0%)" in result.output
    assert "infra cost modeled; memory lever not available locally" in result.output


def test_dry_run_accepts_a_plan_within_half_the_budget() -> None:
    """Sixteen planned tasks at 0.0034 each fit in half of 10 USD."""
    result = _RUNNER.invoke(app, ["dry-run", "--tasks", "2"], obj=_deps("10"))
    assert result.exit_code == 0, result.output
    assert "projected model usd for 16 tasks: 0.0544" in result.output
    assert "ok: the plan fits" in result.output


def test_dry_run_refuses_a_plan_over_half_the_budget() -> None:
    """The same plan against 0.05 USD is refused with exit code 1."""
    result = _RUNNER.invoke(app, ["dry-run", "--tasks", "2"], obj=_deps("0.05"))
    assert result.exit_code == 1
    assert "refusing" in result.output


def test_costwise_errors_become_a_message_and_exit_code_two() -> None:
    """A configuration error from building the stack is reported without a traceback."""

    def failing(kind: RunnerKind) -> AbstractContextManager[EvalStack]:
        """Refuse every runner."""
        raise ConfigError(f"no {kind.value} runner")

    result = _RUNNER.invoke(
        app,
        ["eval", "baseline", "--run-id", "r1", "--runner", "lambda"],
        obj=_deps(eval_stack=failing),
    )
    assert result.exit_code == 2
    assert "error: no lambda runner" in result.output

    unconfigured = _RUNNER.invoke(app, ["eval", "baseline", "--run-id", "r1"], obj="not deps")
    assert unconfigured.exit_code == 2
    assert "CLI dependencies are not configured" in unconfigured.output


def test_fixtures_build_reports_failures_with_exit_code_one(tmp_path: Path) -> None:
    """A domain the source does not know is a failure; comments and blanks are skipped."""
    domains = tmp_path / "domains.txt"
    domains.write_text("# list\na.example.com\n\nb.example.com\n", encoding="utf-8")
    store = InMemoryFixtureStore()
    result = _RUNNER.invoke(
        app, ["fixtures", "build", "--domains-file", str(domains)], obj=_deps(store=store)
    )
    assert result.exit_code == 1
    assert "fetched=1 skipped=0 failed=1" in result.output
    assert store.domains() == ["a.example.com"]

    missing = _RUNNER.invoke(
        app, ["fixtures", "build", "--domains-file", str(tmp_path / "none.txt")], obj=_deps()
    )
    assert missing.exit_code == 2
    assert "cannot read" in missing.output


def test_fixtures_label_counts_heldout_and_fits() -> None:
    """Four clear fits and four companies missing data are labeled with two held out."""
    store = InMemoryFixtureStore()
    for index in range(4):
        fit = f"fit{index}.example.com"
        store.save_fetch(fit, _fetch(fit, 300, "series_a", 20))
        gap = f"gap{index}.example.com"
        store.save_fetch(gap, _fetch(gap, 300, None, None))
    result = _RUNNER.invoke(app, ["fixtures", "label"], obj=_deps(store=store))
    assert result.exit_code == 0, result.output
    assert "labeled=8 heldout=2 expected_fit=4" in result.output


def test_main_runs_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """The console entry point runs the Typer app."""
    monkeypatch.setattr("sys.argv", ["costwise", "--help"])
    with pytest.raises(SystemExit) as exited:
        cli_main.main()
    assert exited.value.code == 0
