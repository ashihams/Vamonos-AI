"""Shared CLI helpers: dependency lookup, error handling, and report lines."""

from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic import ValidationError

from costwise.bootstrap import CliDeps
from costwise.domain.config import Lever
from costwise.domain.errors import CostwiseError
from costwise.domain.task import InfraCostSource
from costwise.ports.runner import RunnerCapabilities
from costwise.services.baseline import PlanProjection, RunReport

USAGE_ERROR = 2
MODELED_INFRA_NOTE = "infra cost modeled; memory lever not available locally"


def cli_deps(ctx: typer.Context) -> CliDeps:
    """Return the dependencies the root callback stored on the context."""
    deps = ctx.find_root().obj
    if not isinstance(deps, CliDeps):
        raise CostwiseError("CLI dependencies are not configured")
    return deps


@contextmanager
def reported_errors() -> Iterator[None]:
    """Turn costwise and settings errors into a one-line message and exit code 2.

    Settings errors list field names only, because validation messages can echo values.
    """
    try:
        yield
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        typer.echo(f"error: missing or invalid settings: {', '.join(fields)}", err=True)
        raise typer.Exit(USAGE_ERROR) from None
    except CostwiseError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(USAGE_ERROR) from None


def report_lines(report: RunReport) -> list[str]:
    """Return the run counts and costs as display lines."""
    rate = report.successes / report.completed if report.completed else 0.0
    lines = [
        f"tasks: {report.completed} of {report.requested} completed, {report.errors} with errors",
        f"success: {report.successes} ({rate:.1%})",
        f"cost usd: model {report.model_usd:.6f}, infra {report.infra_usd:.6f}, "
        f"data {report.data_usd:.6f}, total {report.total_usd:.6f}",
    ]
    if report.completed < report.requested:
        lines.append("stopped early: the budget guard tripped")
    return lines


def capability_lines(capabilities: RunnerCapabilities) -> list[str]:
    """Return the modeled-infrastructure note when the runner cannot change memory."""
    modeled = capabilities.infra_source is InfraCostSource.MODELED
    if modeled and Lever.LAMBDA_MEMORY not in capabilities.levers:
        return [MODELED_INFRA_NOTE]
    return []


def projection_lines(projection: PlanProjection) -> list[str]:
    """Return the measured per-task cost and the full-plan projection as display lines."""
    return [
        f"measured per task usd: model {projection.model_usd_per_task:.6f}, "
        f"total {projection.total_usd_per_task:.6f}",
        f"projected model usd for {projection.planned_tasks} tasks: "
        f"{projection.projected_model_usd:.4f}",
        f"remaining model budget usd: {projection.remaining_budget_usd:.4f}",
    ]
