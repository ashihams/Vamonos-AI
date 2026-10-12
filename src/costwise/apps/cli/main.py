"""costwise command-line entry point."""

import typer

from costwise.apps.cli.commands_eval import dry_run, eval_app
from costwise.apps.cli.commands_fixtures import fixtures_app
from costwise.apps.cli.commands_optimize import optimize
from costwise.bootstrap import default_cli_deps
from costwise.logging_setup import configure_logging

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Cut the cost of an AI app.")
app.add_typer(eval_app, name="eval")
app.add_typer(fixtures_app, name="fixtures")
app.command("dry-run")(dry_run)
app.command("optimize")(optimize)


@app.callback()
def root(ctx: typer.Context) -> None:
    """Configure logging and the default dependencies unless a caller supplied them."""
    configure_logging()
    if ctx.obj is None:
        ctx.obj = default_cli_deps()


def main() -> None:
    """Run the CLI."""
    app()
