"""OtelSink against the in-memory span exporter and metric reader."""

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
from costwise.domain.guardrails import CheckOutcome, GuardrailResult
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.domain.task import ModelTier, TaskResult
from tests.testing_fakes import SteppingClock
from tests.unit.domain.builders import CallSpec, ResultSpec, make_call, make_result, make_summary

_START = 1_700_000_000_000_000_000
_MS = 1_000_000


def _sink(
    with_metrics: bool = False,
) -> tuple[OtelSink, InMemorySpanExporter, InMemoryMetricReader]:
    """Return a sink over in-memory exporters."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meters = MeterProvider(metric_readers=[reader]) if with_metrics else None
    return OtelSink(provider, meters, SteppingClock(_START, _MS)), exporter, reader


def _task(error: str | None = None) -> TaskResult:
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
    return make_result(
        ResultSpec(calls=calls, total_latency_ms=1250, error=error, started_at_ns=_START)
    )


def _by_name(spans: tuple[ReadableSpan, ...]) -> dict[str, ReadableSpan]:
    """Index finished spans by name."""
    return {span.name: span for span in spans}


def test_task_span_tree_times_and_attributes() -> None:
    """One root span per task and one nested child per call, with explicit timestamps."""
    sink, exporter, _ = _sink()
    result = _task()
    sink.record_task("run-1", result)
    spans = _by_name(exporter.get_finished_spans())
    root = spans[attr.TASK_SPAN]
    cheap = spans["chat cheap-model"]
    strong = spans["chat strong-model"]
    assert root.parent is None
    assert root.start_time == _START
    assert root.end_time == _START + 1250 * _MS
    for child in (cheap, strong):
        assert child.parent is not None
        assert child.parent.span_id == root.context.span_id
        assert child.context.trace_id == root.context.trace_id
    assert cheap.start_time == _START + 5 * _MS
    assert cheap.end_time == _START + 305 * _MS
    assert strong.start_time == _START + 320 * _MS
    assert dict(root.attributes or {}) == {
        attr.RUN_ID: "run-1",
        attr.TASK_ID: result.request.task_id,
        attr.CONFIG_VERSION: result.config_version,
        attr.TASK_CATEGORY: result.difficulty.value,
        attr.SPLIT: result.request.split.value,
        attr.SUCCESS: "true" if result.success else "false",
        attr.DATA_CACHE_HIT: "false",
        attr.INFRA_SOURCE: result.infra_source.value,
        attr.COST_MODEL_USD: float(result.costs.model_usd),
        attr.COST_INFRA_USD: float(result.costs.infra_usd),
        attr.COST_DATA_USD: float(result.costs.data_usd),
    }
    assert dict(cheap.attributes or {}) == {
        attr.GEN_AI_OPERATION: "chat",
        attr.GEN_AI_REQUEST_MODEL: "cheap-model",
        attr.GEN_AI_INPUT_TOKENS: 100,
        attr.GEN_AI_OUTPUT_TOKENS: 20,
        attr.MODEL_TIER: "cheap",
    }
    assert root.status.status_code is StatusCode.UNSET


def test_failed_task_marks_the_root_span_as_error() -> None:
    """An invocation error becomes an ERROR status with the message."""
    sink, exporter, _ = _sink()
    sink.record_task("run-1", _task(error="LLMError: model call returned status 400"))
    root = _by_name(exporter.get_finished_spans())[attr.TASK_SPAN]
    assert root.status.status_code is StatusCode.ERROR
    assert root.status.description == "LLMError: model call returned status 400"


def _iteration(guardrails: GuardrailResult | None) -> IterationRecord:
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
        decision=ApprovalDecision(approved=True, note="ok"),
        baseline_version=1,
        candidate_version=2,
        candidate_summary=None,
        guardrails=guardrails,
        accepted=False,
        reason="held-out success dropped",
    )


def test_iteration_span_with_guardrail_children() -> None:
    """Each guardrail check is a child span with a passed flag and an OK or ERROR status."""
    sink, exporter, _ = _sink()
    checks = (
        CheckOutcome(name="eval_success", passed=True, detail="no drop"),
        CheckOutcome(name="heldout_success", passed=False, detail="dropped 5 pp"),
    )
    sink.record_iteration("run-1", _iteration(GuardrailResult(passed=False, checks=checks)))
    spans = _by_name(exporter.get_finished_spans())
    parent = spans[attr.ITERATION_SPAN]
    assert parent.parent is None
    assert dict(parent.attributes or {}) == {
        attr.RUN_ID: "run-1",
        attr.ITERATION: 2,
        attr.LEVER: "routing",
        attr.DECISION: "approved",
        attr.ACCEPTED: "false",
        attr.REASON: "held-out success dropped",
    }
    passed = spans["guardrail eval_success"]
    failed = spans["guardrail heldout_success"]
    assert passed.parent is not None
    assert passed.parent.span_id == parent.context.span_id
    assert (passed.attributes or {})[attr.GUARDRAIL_PASSED] == "true"
    assert passed.status.status_code is StatusCode.OK
    assert (failed.attributes or {})[attr.GUARDRAIL_PASSED] == "false"
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.status.description == "dropped 5 pp"


def test_iteration_without_guardrails_has_no_children() -> None:
    """A rejected-by-human iteration has no guardrail spans."""
    sink, exporter, _ = _sink()
    sink.record_iteration("run-1", _iteration(None))
    assert [span.name for span in exporter.get_finished_spans()] == [attr.ITERATION_SPAN]


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
