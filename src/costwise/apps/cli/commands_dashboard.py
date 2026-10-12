"""dashboard command: export stored runs for the web dashboard."""

from pathlib import Path
from typing import Annotated

import typer

from costwise.apps.cli.support import cli_deps, reported_errors

DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_OUT = Path("dashboard/public/data/dashboard.json")


def dashboard(
    ctx: typer.Context,
    run_ids: Annotated[
        list[str] | None,
        typer.Option("--run-id", help="Run to export; repeat it. Default: every optimized run."),
    ] = None,
    runs_dir: Annotated[Path, typer.Option(help="Directory that holds the runs.")] = (
        DEFAULT_RUNS_DIR
    ),
    out: Annotated[Path, typer.Option(help="JSON file the dashboard reads.")] = DEFAULT_OUT,
) -> None:
    """Write every version's stats, iterations, and tasks to the dashboard's data file."""
    with reported_errors():
        exported = cli_deps(ctx).dashboard_service(runs_dir, out).export(run_ids or [])
    typer.echo(
        f"dashboard data written to {exported.location} "
        f"({exported.runs} runs, {exported.tasks} tasks)"
    )
