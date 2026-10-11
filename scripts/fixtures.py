"""Build or label company fixtures until the Stage 6 CLI exists.

Usage:
    uv run python scripts/fixtures.py build --domains-file domains.txt
    uv run python scripts/fixtures.py label
"""

import argparse
import logging
import sys
from pathlib import Path

import httpx

from costwise.adapters.data.crustdata_client import CrustdataClient
from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.adapters.storage.yaml_loaders import load_icp_rule, load_workload_policy
from costwise.logging_setup import configure_logging
from costwise.services.fixtures import FixtureService
from costwise.settings import CrustdataSettings

_LOG = logging.getLogger("costwise.scripts.fixtures")


def main(argv: list[str]) -> int:
    """Run the build or label command and return the exit code."""
    parser = argparse.ArgumentParser(description="Build or label company fixtures.")
    parser.add_argument("command", choices=["build", "label"])
    parser.add_argument("--domains-file", type=Path, default=Path("fixtures/domains.txt"))
    parser.add_argument("--fixtures-dir", type=Path, default=Path("fixtures"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    args = parser.parse_args(argv)
    configure_logging()
    service = FixtureService(JsonFixtureStore(args.fixtures_dir))
    if args.command == "build":
        return _build(service, args.domains_file)
    return _label(service, args.config_dir)


def _build(service: FixtureService, domains_file: Path) -> int:
    """Fetch every listed domain that is not stored yet."""
    lines = domains_file.read_text(encoding="utf-8").splitlines()
    domains = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    settings = CrustdataSettings()
    with httpx.Client() as http:
        report = service.build(domains, CrustdataClient(http, settings.crustdata_api_key))
    _LOG.info(
        "fixtures fetched=%d skipped=%d failed=%d",
        len(report.fetched),
        len(report.skipped),
        len(report.failed),
    )
    return 1 if report.failed else 0


def _label(service: FixtureService, config_dir: Path) -> int:
    """Label stored fixtures with the ICP rule and the workload held-out settings."""
    rule = load_icp_rule(config_dir / "icp.yaml")
    workload = load_workload_policy(config_dir / "policy.yaml")
    labels = service.label(rule, workload.heldout_count, workload.seed)
    heldout = sum(1 for label in labels.values() if label.split.value == "heldout")
    fits = sum(1 for label in labels.values() if label.expected_fit)
    _LOG.info("labeled=%d heldout=%d expected_fit=%d", len(labels), heldout, fits)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
