"""report command: the evidence pack and cfo.ai inputs for one run."""

from pathlib import Path
from typing import Annotated

import typer

from costwise.apps.cli.support import bundle_lines, cli_deps, reported_errors

DEFAULT_RUNS_DIR = Path("runs")


def report(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run directory name under runs/.")],
    runs_dir: Annotated[Path, typer.Option(help="Directory that holds the runs.")] = (
        DEFAULT_RUNS_DIR
    ),
) -> None:
    """Write report.md, trajectory.csv, cfo_inputs.json, and trajectory.mmd for a run."""
    with reported_errors():
        bundle = cli_deps(ctx).report_service(runs_dir).build(run_id)
    for line in bundle_lines(bundle):
        typer.echo(line)
