"""Shared CLI helpers: dependency lookup, error handling, and report lines."""

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import typer
from pydantic import ValidationError

from costwise.bootstrap import CliDeps
from costwise.domain.config import Lever
from costwise.domain.errors import CostwiseError
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import InfraCostSource
from costwise.ports.runner import RunnerCapabilities
from costwise.services.baseline import PlanProjection, RunReport
from costwise.services.report import ReportBundle
from costwise.services.report_format import change_pct, signed_pct, usd

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


def iteration_lines(records: Sequence[IterationRecord], start_version: int) -> list[str]:
    """Return one line per iteration and the config version that ended up accepted."""
    lines: list[str] = []
    accepted_version = start_version
    for record in records:
        change = f"{record.proposal.lever.value}={json.dumps(record.proposal.new_value)}"
        lines.append(f"iteration {record.iteration}: {change} {_outcome(record)} ({record.reason})")
        if record.accepted and record.candidate_version is not None:
            accepted_version = record.candidate_version
    if not records:
        lines.append("no iterations ran")
    lines.append(f"accepted config version: {accepted_version}")
    return lines


def _outcome(record: IterationRecord) -> str:
    """Return what happened to the proposal in a few words."""
    if not record.decision.approved:
        return "declined"
    return "kept" if record.accepted else "rolled back"


def bundle_lines(bundle: ReportBundle) -> list[str]:
    """Return where the report went and the headline unit-cost change."""
    base, final = bundle.data.baseline, bundle.data.final
    change = signed_pct(change_pct(base.cost_per_successful_task, final.cost_per_successful_task))
    return [
        f"report written to {bundle.location}",
        f"cost per successful task usd: v{base.version} {usd(base.cost_per_successful_task)}"
        f" -> v{final.version} {usd(final.cost_per_successful_task)} ({change})",
    ]


def projection_lines(projection: PlanProjection) -> list[str]:
    """Return the measured per-task cost and the full-plan projection as display lines."""
    return [
        f"measured per task usd: model {projection.model_usd_per_task:.6f}, "
        f"total {projection.total_usd_per_task:.6f}",
        f"projected model usd for {projection.planned_tasks} tasks: "
        f"{projection.projected_model_usd:.4f}",
        f"remaining model budget usd: {projection.remaining_budget_usd:.4f}",
    ]
