"""Re-export a stored run's task and iteration traces to neatlogs. No model calls are made.

Usage (NEATLOGS_API_KEY in the environment or .env):
    uv run python scripts/replay_neatlogs.py --run-id demo

Traces come from runs/<run id>/results_v<n>.jsonl and iterations.jsonl as they were
recorded. Task spans keep their original start times; iteration spans are stamped now.
"""

import argparse
import logging
import sys
from pathlib import Path

from costwise.adapters.storage.jsonl_run_store import JsonlRunStore
from costwise.adapters.storage.yaml_loaders import load_price_book
from costwise.adapters.system_clock import SystemClock
from costwise.adapters.telemetry.exporters import neatlogs_tracer_provider
from costwise.adapters.telemetry.otel_sink import OtelSink
from costwise.bootstrap import env_file
from costwise.domain.errors import MissingStoreError
from costwise.logging_setup import configure_logging
from costwise.ports.storage import RunStore
from costwise.ports.telemetry import TelemetrySink
from costwise.settings import NeatlogsSettings

_LOG = logging.getLogger("costwise.scripts.replay_neatlogs")


def replay(run_id: str, runs: RunStore, sink: TelemetrySink) -> tuple[int, int]:
    """Send every stored version's results, then every iteration; return both counts."""
    tasks = 0
    version = 1
    while True:
        try:
            results = runs.load_results(run_id, version)
        except MissingStoreError:
            break
        for result in results:
            sink.record_task(run_id, result)
        tasks += len(results)
        version += 1
    iterations = runs.load_iterations(run_id)
    for record in iterations:
        sink.record_iteration(run_id, record)
    return tasks, len(iterations)


def main() -> int:
    """Replay one run from the runs directory and flush before exit."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    args = parser.parse_args()
    configure_logging()
    settings = NeatlogsSettings(_env_file=env_file())
    provider = neatlogs_tracer_provider(settings.neatlogs_api_key)
    prices = load_price_book(args.config_dir / "pricing.yaml")
    sink = OtelSink(provider, None, SystemClock(), prices)
    tasks, iterations = replay(args.run_id, JsonlRunStore(args.runs_dir), sink)
    sink.flush()
    provider.shutdown()
    _LOG.info("replayed run_id=%s tasks=%d iterations=%d", args.run_id, tasks, iterations)
    return 0


if __name__ == "__main__":
    sys.exit(main())
