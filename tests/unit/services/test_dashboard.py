"""Dashboard export: which runs, versions, and task fields end up in the document."""

import json

import pytest

from costwise.domain.errors import CostwiseError
from costwise.domain.task import QualificationAnswer
from costwise.services.dashboard import DashboardData, DashboardService, dashboard_task
from tests.testing_fakes import InMemoryRunStore, RecordingDashboardSink
from tests.unit.domain.builders import ResultSpec, make_result
from tests.unit.services.report_support import RUN_ID, scenario_store


def test_named_run_exports_every_evaluated_version_with_its_tasks() -> None:
    """The scenario evaluates v1 to v3, four tasks each; the declined proposal adds none."""
    data = DashboardService(scenario_store(), RecordingDashboardSink()).collect([RUN_ID])
    (run,) = data.runs
    assert [stats.version for stats in run.report.versions] == [1, 2, 3]
    assert run.report.final.version == 2
    assert len(run.report.iterations) == 3
    assert [task.version for task in run.tasks] == [1] * 4 + [2] * 4 + [3] * 4


def test_without_names_every_run_with_iterations_is_exported() -> None:
    """An empty selection falls back to the store's optimized runs."""
    data = DashboardService(scenario_store(), RecordingDashboardSink()).collect([])
    assert [run.report.run_id for run in data.runs] == [RUN_ID]


def test_no_optimized_runs_is_an_error() -> None:
    """With nothing to show, the export refuses rather than writing an empty document."""
    service = DashboardService(InMemoryRunStore(), RecordingDashboardSink())
    with pytest.raises(CostwiseError, match="no runs with iterations"):
        service.collect([])


def test_export_writes_one_document_and_counts_runs_and_tasks() -> None:
    """The written JSON parses back into the same data."""
    sink = RecordingDashboardSink()
    exported = DashboardService(scenario_store(), sink).export([RUN_ID])
    assert (exported.location, exported.runs, exported.tasks) == ("memory://dashboard.json", 1, 12)
    (body,) = sink.bodies
    parsed = DashboardData.model_validate_json(body)
    assert parsed.runs[0].report.run_id == RUN_ID
    assert json.loads(body)["runs"][0]["tasks"][0]["costs"]["model_usd"] == "0.01"


def test_task_row_carries_the_answer_or_the_error() -> None:
    """Answered tasks keep fit and reasons; failed ones keep the error and no answer."""
    result = make_result(ResultSpec(task_id="t-1"))
    answer = QualificationAnswer(
        icp_fit=True, reasons=("fits",), headcount_band="201-500", stage="series_a"
    )
    invocation = result.invocation.model_copy(update={"answer": answer})
    answered = dashboard_task(result.model_copy(update={"invocation": invocation}))
    assert (answered.icp_fit, answered.reasons, answered.error) == (True, ("fits",), None)
    failed = dashboard_task(make_result(ResultSpec(task_id="t-2", error="boom")))
    assert (failed.icp_fit, failed.reasons, failed.error) == (None, (), "boom")
