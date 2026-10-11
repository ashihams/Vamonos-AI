"""Bootstrap factories that need no network."""

from decimal import Decimal
from pathlib import Path

import pytest

from costwise.adapters.data.crustdata_client import CrustdataClient
from costwise.apps.cli.support import capability_lines, report_lines
from costwise.bootstrap import build_fixture_stack, default_cli_deps, open_crustdata_source
from costwise.domain.task import InfraCostSource
from costwise.ports.runner import RunnerCapabilities
from costwise.services.baseline import RunReport

_REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_fixture_stack_reads_rule_and_workload(tmp_path: Path) -> None:
    """The fixture stack loads the ICP rule and workload settings from config files."""
    stack = build_fixture_stack(tmp_path, _REPO_CONFIG)
    assert stack.workload.n_requests == 40
    assert stack.rule.max_employees == 1000
    assert default_cli_deps().fixture_stack is build_fixture_stack


def test_crustdata_source_reads_the_key_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key comes from .env in the working directory; unrelated keys are ignored."""
    monkeypatch.delenv("CRUSTDATA_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "CRUSTDATA_API_KEY=crust-test-only\nLITELLM_LICENSE=unrelated\n", encoding="utf-8"
    )
    with open_crustdata_source() as source:
        assert isinstance(source, CrustdataClient)


def test_report_and_capability_lines_cover_early_stop_and_measured_infra() -> None:
    """An early stop is called out; a measured-infra runner gets no modeled note."""
    zero = Decimal(0)
    report = RunReport(
        requested=5,
        completed=3,
        successes=3,
        errors=0,
        model_usd=zero,
        infra_usd=zero,
        data_usd=zero,
    )
    assert "stopped early: the budget guard tripped" in report_lines(report)
    measured = RunnerCapabilities(levers=frozenset(), infra_source=InfraCostSource.MEASURED)
    assert capability_lines(measured) == []
