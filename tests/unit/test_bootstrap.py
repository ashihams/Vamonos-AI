"""Bootstrap factories that need no network."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from costwise.adapters.data.crustdata_client import CrustdataClient
from costwise.adapters.storage.jsonl_run_store import JsonlRunStore
from costwise.adapters.telemetry.null_sink import NullSink
from costwise.adapters.telemetry.otel_sink import OtelSink
from costwise.apps.cli.support import capability_lines, report_lines
from costwise.bootstrap import (
    build_fixture_stack,
    build_report_service,
    build_telemetry,
    default_cli_deps,
    open_crustdata_source,
)
from costwise.domain.task import InfraCostSource
from costwise.ports.runner import RunnerCapabilities
from costwise.services.baseline import RunReport
from costwise.settings import AwsSettings, EvalSettings
from tests.testing_fakes import FixedClock
from tests.unit.services.report_support import version_results

_REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_fixture_stack_reads_rule_and_workload(tmp_path: Path) -> None:
    """The fixture stack loads the ICP rule and workload settings from config files."""
    stack = build_fixture_stack(tmp_path, _REPO_CONFIG)
    assert stack.workload.n_requests == 28
    assert stack.rule.max_employees == 1000
    assert default_cli_deps().fixture_stack is build_fixture_stack


def test_report_service_reads_and_writes_the_runs_directory(tmp_path: Path) -> None:
    """The wired report service reads JSONL results and writes the report beside them."""
    JsonlRunStore(tmp_path).save_results("r1", 1, version_results(1, "0.01", (True,) * 4))
    bundle = build_report_service(tmp_path).build("r1")
    folder = tmp_path / "r1" / "report"
    assert bundle.location == folder.as_posix()
    assert sorted(p.name for p in folder.iterdir()) == [
        "cfo_inputs.json",
        "report.md",
        "trajectory.csv",
        "trajectory.mmd",
    ]
    assert default_cli_deps().report_service is build_report_service


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


def test_telemetry_is_otel_with_a_neatlogs_key_and_null_without() -> None:
    """The neatlogs key switches telemetry from the null sink to the OTel sink."""
    base = EvalSettings(
        litellm_base_url="https://llm.example.test/v1",
        litellm_api_key=SecretStr("sk-test-only"),
        model_budget_usd=Decimal(5),
        neatlogs_api_key=None,
        otel_collector_endpoint="",
    )
    assert isinstance(build_telemetry(base, FixedClock(1)), NullSink)
    keyed = base.model_copy(update={"neatlogs_api_key": SecretStr("neat-test-only")})
    sink = build_telemetry(keyed, FixedClock(1))
    assert isinstance(sink, OtelSink)
    sink.flush()


def test_empty_environment_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank lines copied from .env.example fall back to defaults instead of empty strings."""
    for name in ("NEATLOGS_API_KEY", "AWS_REGION", "LAMBDA_FUNCTION_NAME"):
        monkeypatch.setenv(name, "")
    settings = EvalSettings(
        litellm_base_url="https://llm.example.test/v1",
        litellm_api_key=SecretStr("sk-test-only"),
        model_budget_usd=Decimal(5),
    )
    assert settings.neatlogs_api_key is None
    assert settings.aws_region == "us-east-1"
    assert AwsSettings().lambda_function_name == "costwise-qualify"


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
