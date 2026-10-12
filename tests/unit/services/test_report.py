"""Report service: collection, golden files, source tags, and held-out labels."""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from costwise.domain.errors import MissingStoreError
from costwise.domain.task import InfraCostSource
from costwise.services.report import ReportService
from costwise.services.report_data import version_stats
from costwise.services.report_format import change_pct, infra_source, source_notes
from costwise.services.report_render import render_files
from tests.testing_fakes import InMemoryRunStore, RecordingReportSink
from tests.unit.domain.builders import ResultSpec, make_result
from tests.unit.services.report_support import RUN_ID, scenario_service, version_results

GOLDEN = Path(__file__).parents[2] / "golden" / "report"
MONEY = re.compile(r"\d+\.\d{6}")


def _built_files() -> dict[str, str]:
    """Publish the scenario and return the files written."""
    service, sink = scenario_service()
    service.build(RUN_ID)
    return sink.reports[RUN_ID]


@pytest.mark.parametrize(
    "name", ["report.md", "trajectory.csv", "cfo_inputs.json", "trajectory.mmd"]
)
def test_report_files_match_golden(name: str) -> None:
    """Each rendered file is byte-for-byte the reviewed golden copy."""
    expected = (GOLDEN / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert _built_files()[name] == expected


def test_publish_returns_the_sink_location_and_final_version() -> None:
    """Publishing reports where the files went and which version was kept."""
    service, _ = scenario_service()
    bundle = service.build(RUN_ID)
    assert bundle.location == f"memory://{RUN_ID}/report"
    assert bundle.data.final.version == 2
    assert [v.status for v in bundle.data.versions] == ["baseline", "kept", "rolled back"]


def test_every_cost_line_in_the_report_has_a_source_tag() -> None:
    """Any report line that shows a dollar figure says where the number came from."""
    lines = [line for line in _built_files()["report.md"].splitlines() if MONEY.search(line)]
    assert lines
    assert all("[source: " in line for line in lines)


def test_heldout_numbers_are_labeled() -> None:
    """Held-out success appears only on rows and columns that say held-out."""
    files = _built_files()
    heldout_rows = [line for line in files["report.md"].splitlines() if "held-out split" in line]
    assert heldout_rows == [
        "| Success rate, held-out split (never shown to the optimizer) | 100.0% | 100.0% |"
    ]
    assert "heldout_success_rate" in files["trajectory.csv"].splitlines()[0]
    assert json.loads(files["cfo_inputs.json"])["optimized"]["success_rate_heldout"] == 1.0


def test_no_iterations_keeps_the_baseline_as_final() -> None:
    """A run with only a baseline reports v1 twice and says no iterations ran."""
    runs = InMemoryRunStore()
    runs.save_results(RUN_ID, 1, version_results(1, "0.01", (True, True, False, True)))
    sink = RecordingReportSink()
    data = ReportService(runs, sink).build(RUN_ID).data
    assert data.final == data.baseline
    assert "No iterations ran." in sink.reports[RUN_ID]["report.md"]


def test_missing_baseline_raises() -> None:
    """A run without stored baseline results cannot be reported."""
    with pytest.raises(MissingStoreError):
        ReportService(InMemoryRunStore(), RecordingReportSink()).collect("absent")


def test_version_without_successes_has_no_unit_cost() -> None:
    """Zero successes leaves cost per successful task undefined everywhere it is shown."""
    stats = version_stats(1, "baseline", version_results(1, "0.01", (False,) * 4))
    assert stats.cost_per_successful_task is None
    service, _ = scenario_service()
    data = service.collect(RUN_ID).model_copy(update={"baseline": stats, "final": stats})
    files = render_files(data.model_copy(update={"versions": (stats,)}))
    assert (
        "| Cost per successful task, USD [source: model + infra + data] | n/a | n/a | n/a |"
        in (files["report.md"])
    )
    assert json.loads(files["cfo_inputs.json"])["cost_per_successful_task_change_pct"] is None
    assert files["trajectory.csv"].splitlines()[1].split(",")[4] == ""
    assert "line []" in files["trajectory.mmd"]


def test_empty_version_has_no_rates_or_latency() -> None:
    """A version with no results reports counts of zero and no rates or latency."""
    stats = version_stats(2, "kept", [])
    assert (stats.tasks, stats.eval_success_rate, stats.heldout_success_rate) == (0, None, None)
    assert stats.p95_latency_ms is None
    assert infra_source(stats) == "no tasks ran"


def test_infra_source_reflects_measured_and_mixed_results() -> None:
    """Measured, modeled, and mixed infra sources get different tags and notes."""
    measured = version_stats(
        2, "kept", [make_result(ResultSpec(infra_source=InfraCostSource.MEASURED))]
    )
    modeled = version_stats(1, "baseline", [make_result()])
    assert infra_source(measured) == "measured from Lambda REPORT lines"
    assert infra_source(modeled, measured) == "mixed: measured and modeled"
    assert "REPORT line" in source_notes(measured)[1]
    assert "with care" in source_notes(modeled, measured)[1]


def test_change_pct_is_undefined_without_a_positive_baseline() -> None:
    """The percentage change needs both numbers and a non-zero baseline."""
    assert change_pct(Decimal("0.02"), Decimal("0.015")) == Decimal("-25.0")
    assert change_pct(Decimal(0), Decimal("0.01")) is None
    assert change_pct(None, Decimal("0.01")) is None
