"""fixtures build and label commands."""

from pathlib import Path
from typing import Annotated

import typer

from costwise.apps.cli.support import USAGE_ERROR, cli_deps, reported_errors
from costwise.domain.task import Split

fixtures_app = typer.Typer(no_args_is_help=True, help="Fetch and label company fixtures.")

FAILED_EXIT = 1
_FixturesDir = Annotated[Path, typer.Option(help="Fixture directory.")]
_ConfigDir = Annotated[Path, typer.Option(help="Config directory.")]


@fixtures_app.command("build")
def build(
    ctx: typer.Context,
    domains_file: Annotated[Path, typer.Option(help="One domain per line.")] = Path(
        "fixtures/domains.txt"
    ),
    fixtures_dir: _FixturesDir = Path("fixtures"),
    config_dir: _ConfigDir = Path("config"),
) -> None:
    """Fetch every listed domain from Crustdata that is not stored yet."""
    try:
        lines = domains_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        typer.echo(f"error: cannot read {domains_file}", err=True)
        raise typer.Exit(USAGE_ERROR) from None
    domains = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    deps = cli_deps(ctx)
    with reported_errors():
        stack = deps.fixture_stack(fixtures_dir, config_dir)
        with deps.crustdata_source() as source:
            report = stack.service.build(domains, source)
    typer.echo(
        f"fetched={len(report.fetched)} skipped={len(report.skipped)} failed={len(report.failed)}"
    )
    if report.failed:
        raise typer.Exit(FAILED_EXIT)


@fixtures_app.command("label")
def label(
    ctx: typer.Context,
    fixtures_dir: _FixturesDir = Path("fixtures"),
    config_dir: _ConfigDir = Path("config"),
) -> None:
    """Label stored fixtures with the ICP rule and choose the held-out split."""
    with reported_errors():
        stack = cli_deps(ctx).fixture_stack(fixtures_dir, config_dir)
        labels = stack.service.label(stack.rule, stack.workload.heldout_count, stack.workload.seed)
    heldout = sum(1 for item in labels.values() if item.split is Split.HELDOUT)
    fits = sum(1 for item in labels.values() if item.expected_fit)
    typer.echo(f"labeled={len(labels)} heldout={heldout} expected_fit={fits}")
