"""optimize command: the approval loop."""

from typing import Annotated

import typer

from costwise.apps.cli.support import cli_deps, iteration_lines, reported_errors
from costwise.bootstrap import RunnerKind

DEFAULT_ITERATIONS = 3


def optimize(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run directory name under runs/.")],
    iterations: Annotated[int, typer.Option(min=1, help="Most iterations to try.")] = (
        DEFAULT_ITERATIONS
    ),
    auto_approve: Annotated[
        bool, typer.Option("--auto-approve", help="Approve every proposal without asking.")
    ] = False,
    runner: Annotated[RunnerKind, typer.Option(help="Where tasks run.")] = RunnerKind.LOCAL,
) -> None:
    """Propose, approve, re-run, and keep or roll back one lever change per iteration."""
    with reported_errors():
        deps = cli_deps(ctx)
        with deps.eval_stack(runner) as stack:
            service = stack.iteration_with(deps.approver(auto_approve))
            records = service.run(run_id, stack.config, stack.requests, iterations)
            start_version = stack.config.version
    for line in iteration_lines(records, start_version):
        typer.echo(line)
