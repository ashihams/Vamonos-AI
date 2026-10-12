"""OtelSink against the in-memory span exporter and metric reader."""

import json
from decimal import Decimal

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from costwise.adapters.telemetry import attributes as attr
from costwise.adapters.telemetry.otel_sink import OtelSink
from costwise.domain.config import Lever
from costwise.domain.cost import PriceBook
from costwise.domain.guardrails import CheckOutcome, GuardrailResult
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.domain.task import ModelTier, QualificationAnswer, TaskResult
from tests.testing_fakes import SteppingClock
from tests.unit.domain.builders import (
    CallSpec,
    ResultSpec,
    make_call,
    make_prices,
    make_result,
    make_summary,
)

_START = 1_700_000_000_000_000_000
_MS = 1_000_000
_ANSWER = QualificationAnswer(icp_fit=True, reasons=("fits",), headcount_band="51-200", stage=None)


def _sink(
    with_metrics: bool = False, prices: PriceBook | None = None
) -> tuple[OtelSink, InMemorySpanExporter, InMemoryMetricReader]:
    """Return a sink over in-memory exporters."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meters = MeterProvider(metric_readers=[reader]) if with_metrics else None
    return OtelSink(provider, meters, SteppingClock(_START, _MS), prices), exporter, reader


def _task(error: str | None = None, answered: bool = False) -> TaskResult:
    """Return a task with a cheap call at 5 ms and a strong call at 320 ms."""
    calls = (
        make_call(
            CallSpec(model="cheap-model", tier=ModelTier.CHEAP, latency_ms=300, started_offset_ms=5)
        ),
        make_call(
            CallSpec(
                model="strong-model", tier=ModelTier.STRONG, latency_ms=900, started_offset_ms=320
            )
        ),
    )
    result = make_result(
        ResultSpec(calls=calls, total_latency_ms=1250, error=error, started_at_ns=_START)
    )
    if not answered:
        return result
    invocation = result.invocation.model_copy(update={"answer": _ANSWER})
    return result.model_copy(update={"invocation": invocation})


def _by_name(spans: tuple[ReadableSpan, ...]) -> dict[str, ReadableSpan]:
    """Index finished spans by name."""
    return {span.name: span for span in spans}


def _attrs(span: ReadableSpan) -> dict[str, object]:
    """Return a span's attributes as a plain dict."""
    return dict(span.attributes or {})


def test_task_trace_is_a_workflow_with_tool_llm_and_evaluator_children() -> None:
    """The root carries identity and IO; children nest with explicit timestamps."""
    sink, exporter, _ = _sink(prices=make_prices())
    result = _task()
    sink.record_task("run-1", result)
    spans = _by_name(exporter.get_finished_spans())
    root, data = spans[attr.TASK_SPAN], spans[attr.DATA_SPAN]
    cheap, strong = spans["chat cheap-model"], spans["chat strong-model"]
    score = spans[attr.SCORE_SPAN]
    assert root.parent is None
    assert (root.start_time, root.end_time) == (_START, _START + 1250 * _MS)
    for child in (data, cheap, strong, score):
        assert child.parent is not None
        assert child.parent.span_id == root.context.span_id
    assert (data.start_time, data.end_time) == (_START, _START + 5 * _MS)
    assert (cheap.start_time, cheap.end_time) == (_START + 5 * _MS, _START + 305 * _MS)
    assert strong.start_time == _START + 320 * _MS
    root_attrs = _attrs(root)
    assert root_attrs[attr.SPAN_KIND] == "workflow"
    assert root_attrs[attr.SESSION_ID] == "run-1"
    assert root_attrs[attr.END_USER_ID] == "example.com"
    assert json.loads(str(root_attrs["neatlogs.workflow.input"]))["task_id"] == "task-1"
    assert json.loads(str(root_attrs["neatlogs.workflow.output"])) == {"error": None}
    assert root_attrs[attr.SUCCESS] == "true"
    assert root_attrs[attr.COST_DATA_USD] == float(result.costs.data_usd)
    assert _attrs(data)[attr.SPAN_KIND] == "tool"
    assert json.loads(str(_attrs(data)["neatlogs.tool.output"]))["credits"] == "1"
    assert _attrs(cheap) == {
        attr.SPAN_KIND: "llm",
        attr.LLM_MODEL_NAME: "cheap-model",
        attr.LLM_PROVIDER: "litellm",
        attr.LLM_PROMPT_TOKENS: 100,
        attr.LLM_COMPLETION_TOKENS: 20,
        attr.LLM_TOTAL_TOKENS: 120,
        attr.MODEL_TIER: "cheap",
        attr.LLM_COST_USD: float(Decimal("0.00014")),
    }
    assert _attrs(score)[attr.SPAN_KIND] == "evaluator"
    assert json.loads(str(_attrs(score)["neatlogs.evaluator.output"]))["success"] is True
    assert root.status.status_code is StatusCode.UNSET


def test_the_answer_is_the_output_of_the_root_and_the_last_call() -> None:
    """Only the final call produced the parsed answer."""
    sink, exporter, _ = _sink()
    sink.record_task("run-1", _task(answered=True))
    spans = _by_name(exporter.get_finished_spans())
    expected = _ANSWER.model_dump_json()
    assert _attrs(spans[attr.TASK_SPAN])["neatlogs.workflow.output"] == expected
    assert _attrs(spans["chat strong-model"])["neatlogs.llm.output"] == expected
    assert "neatlogs.llm.output" not in _attrs(spans["chat cheap-model"])


def test_call_cost_is_left_out_without_a_price() -> None:
    """No price book, or an unpriced model, means no cost attribute."""
    sink, exporter, _ = _sink()
    sink.record_task("run-1", _task())
    assert attr.LLM_COST_USD not in _attrs(
        _by_name(exporter.get_finished_spans())["chat cheap-model"]
    )
    priced_sink, priced_exporter, _ = _sink(prices=make_prices())
    unknown = make_result(ResultSpec(calls=(make_call(CallSpec(model="other-model")),)))
    priced_sink.record_task("run-1", unknown)
    other = _by_name(priced_exporter.get_finished_spans())["chat other-model"]
    assert attr.LLM_COST_USD not in _attrs(other)


def test_failed_task_marks_the_root_span_as_error() -> None:
    """An invocation error becomes an ERROR status with the message."""
    sink, exporter, _ = _sink()
    sink.record_task("run-1", _task(error="LLMError: model call returned status 400"))
    spans = _by_name(exporter.get_finished_spans())
    root = spans[attr.TASK_SPAN]
    assert root.status.status_code is StatusCode.ERROR
    assert root.status.description == "LLMError: model call returned status 400"
    assert spans[attr.DATA_SPAN].status.status_code is StatusCode.UNSET


def test_a_task_that_failed_before_any_model_call_blames_the_data_lookup() -> None:
    """With no calls, the lookup span covers the whole task and carries the error."""
    sink, exporter, _ = _sink()
    failed = make_result(
        ResultSpec(calls=(), error="DataError: 503", total_latency_ms=40, started_at_ns=_START)
    )
    sink.record_task("run-1", failed)
    data = _by_name(exporter.get_finished_spans())[attr.DATA_SPAN]
    assert data.end_time == _START + 40 * _MS
    assert data.status.status_code is StatusCode.ERROR


def _iteration(
    guardrails: GuardrailResult | None, approved: bool = True, note: str = "ok"
) -> IterationRecord:
    """Return a rejected routing iteration."""
    return IterationRecord(
        iteration=2,
        proposal=Proposal(
            lever=Lever.ROUTING,
            new_value={"default_tier": "cheap"},
            rationale="r",
            predicted_cost_change_pct=-30.0,
            risk="medium",
        ),
        decision=ApprovalDecision(approved=approved, note=note),
        baseline_version=1,
        candidate_version=2 if approved else None,
        candidate_summary=make_summary(0.5, 900) if approved else None,
        guardrails=guardrails,
        accepted=False,
        reason="held-out success dropped",
    )


def test_iteration_trace_is_an_agent_with_approval_evaluation_and_guardrails() -> None:
    """Approval and each check are GUARDRAIL spans with boolean passed flags."""
    sink, exporter, _ = _sink()
    checks = (
        CheckOutcome(name="eval_success", passed=True, detail="no drop"),
        CheckOutcome(name="heldout_success", passed=False, detail="dropped 5 pp"),
    )
    sink.record_iteration("run-1", _iteration(GuardrailResult(passed=False, checks=checks)))
    spans = _by_name(exporter.get_finished_spans())
    root = spans[attr.ITERATION_SPAN]
    assert root.parent is None
    root_attrs = _attrs(root)
    assert root_attrs[attr.SPAN_KIND] == "agent"
    assert root_attrs[attr.SESSION_ID] == "run-1"
    assert root_attrs[attr.LEVER] == "routing"
    assert json.loads(str(root_attrs["neatlogs.agent.input"]))["lever"] == "routing"
    assert json.loads(str(root_attrs["neatlogs.agent.output"]))["accepted"] is False
    approval = spans[attr.APPROVAL_SPAN]
    assert _attrs(approval)[attr.GUARDRAIL_PASSED] is True
    assert approval.status.status_code is StatusCode.OK
    candidate = _attrs(spans[attr.CANDIDATE_SPAN])
    assert candidate[attr.SPAN_KIND] == "evaluator"
    assert json.loads(str(candidate["neatlogs.evaluator.output"]))["p95_latency_ms"] == 900
    passed, failed = spans["guardrail eval_success"], spans["guardrail heldout_success"]
    assert passed.parent is not None
    assert passed.parent.span_id == root.context.span_id
    assert _attrs(passed)[attr.GUARDRAIL_PASSED] is True
    assert _attrs(failed)[attr.GUARDRAIL_PASSED] is False
    assert _attrs(failed)[attr.GUARDRAIL_REASON] == "dropped 5 pp"
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.status.description == "dropped 5 pp"


def test_a_declined_iteration_has_only_a_blocked_approval() -> None:
    """A human decline blocks at approval; there is no candidate or guardrail span."""
    sink, exporter, _ = _sink()
    sink.record_iteration("run-1", _iteration(None, approved=False, note=""))
    spans = _by_name(exporter.get_finished_spans())
    assert set(spans) == {attr.ITERATION_SPAN, attr.APPROVAL_SPAN}
    approval = spans[attr.APPROVAL_SPAN]
    assert _attrs(approval)[attr.GUARDRAIL_PASSED] is False
    assert approval.status.description == "declined"


def test_summary_gauges_are_labeled_by_run_and_version_only() -> None:
    """Three gauges carry run_id and config_version labels and never a task id."""
    sink, _, reader = _sink(with_metrics=True)
    summary = make_summary(0.75, 1500)
    sink.record_summary("run-1", 3, summary)
    sink.flush()
    data = reader.get_metrics_data()
    assert data is not None
    points = {
        metric.name: list(metric.data.data_points)
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert set(points) == {
        attr.METRIC_COST_PER_TASK,
        attr.METRIC_SUCCESS_RATE,
        attr.METRIC_LATENCY_P95,
    }
    assert points[attr.METRIC_SUCCESS_RATE][0].value == 0.75
    assert points[attr.METRIC_LATENCY_P95][0].value == 1500
    expected_cost = float(summary.totals.total_usd / Decimal(summary.n))
    assert points[attr.METRIC_COST_PER_TASK][0].value == expected_cost
    for series in points.values():
        assert dict(series[0].attributes or {}) == {"run_id": "run-1", "config_version": 3}


def test_summary_without_meter_provider_is_a_no_op() -> None:
    """Without a Collector, summaries are dropped and flush still works."""
    sink, exporter, _ = _sink()
    sink.record_summary("run-1", 1, make_summary(1.0, 10))
    sink.flush()
    assert exporter.get_finished_spans() == ()
