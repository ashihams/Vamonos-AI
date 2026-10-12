"""eval baseline and dry-run commands."""

from typing import Annotated

import typer

from costwise.apps.cli.support import (
    capability_lines,
    cli_deps,
    projection_lines,
    report_lines,
    reported_errors,
)
from costwise.bootstrap import RunnerKind

eval_app = typer.Typer(no_args_is_help=True, help="Evaluate configs on the workload.")

PLANNED_ITERATIONS = 3
OVER_BUDGET_EXIT = 1


@eval_app.command("baseline")
def baseline(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run directory name under runs/.")],
    runner: Annotated[RunnerKind, typer.Option(help="Where tasks run.")] = RunnerKind.LOCAL,
    tasks: Annotated[int | None, typer.Option(min=1, help="Run only the first N requests.")] = None,
) -> None:
    """Evaluate the initial config and store its results."""
    with reported_errors(), cli_deps(ctx).eval_stack(runner) as stack:
        requests = stack.requests if tasks is None else stack.requests[:tasks]
        report = stack.baseline.run(run_id, stack.config, requests)
        lines = report_lines(report) + capability_lines(stack.capabilities)
    for line in lines:
        typer.echo(line)


def dry_run(
    ctx: typer.Context,
    tasks: Annotated[int, typer.Option(min=1, help="Requests to run now.")] = 5,
    run_id: Annotated[str, typer.Option("--run-id")] = "dry-run",
    runner: Annotated[RunnerKind, typer.Option()] = RunnerKind.LOCAL,
    iterations: Annotated[int, typer.Option(min=0, help="Planned optimizer iterations.")] = (
        PLANNED_ITERATIONS
    ),
) -> None:
    """Run a few tasks and refuse if the full plan would use over half the remaining budget."""
    with reported_errors(), cli_deps(ctx).eval_stack(runner) as stack:
        planned = len(stack.requests) * (1 + iterations)
        report, projection = stack.baseline.dry_run(
            run_id, stack.config, stack.requests[:tasks], planned
        )
        lines = report_lines(report) + projection_lines(projection)
    for line in lines:
        typer.echo(line)
    if not projection.within_budget:
        typer.echo("refusing: the plan would use more than half the remaining budget", err=True)
        raise typer.Exit(OVER_BUDGET_EXIT)
    typer.echo("ok: the plan fits within half the remaining budget")
