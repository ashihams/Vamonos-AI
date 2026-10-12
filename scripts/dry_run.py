"""Run the 5-task budget check before spending on a full baseline.

Usage (LITELLM_BASE_URL, LITELLM_API_KEY, and MODEL_BUDGET_USD in the environment or .env):
    uv run python scripts/dry_run.py
    uv run python scripts/dry_run.py --runner lambda

Extra arguments are passed to ``costwise dry-run``. The exit code is 0 when the full
plan fits within half the remaining model budget, 1 when it does not, and 2 for a usage or
settings error.
"""

import sys
from collections.abc import Sequence

from costwise.apps.cli.main import app

DRY_RUN_TASKS = 5


def dry_run_args(extra: Sequence[str]) -> list[str]:
    """Return the CLI arguments for the 5-task dry run followed by any extra ones."""
    return ["dry-run", "--tasks", str(DRY_RUN_TASKS), *extra]


def main() -> None:
    """Run ``costwise dry-run --tasks 5`` with the arguments given to this script."""
    app(args=dry_run_args(sys.argv[1:]), prog_name="dry_run.py")


if __name__ == "__main__":
    main()
