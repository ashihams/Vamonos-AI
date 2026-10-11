"""OpenTelemetry sink: task and iteration spans to neatlogs, summary metrics to a local Collector.

Spans are built driver-side from returned results, with explicit timestamps,
so a remote runner never has to export anything itself.
"""

from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.util.types import Attributes

from costwise.adapters.telemetry import attributes as attr
from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import CallRecord, TaskResult
from costwise.ports.clock import Clock

_NS_PER_MS = 1_000_000
_Setter = Callable[[float, Attributes], None]


class OtelSink:
    """TelemetrySink over a dedicated TracerProvider and an optional MeterProvider."""

    def __init__(
        self, tracer_provider: TracerProvider, meter_provider: MeterProvider | None, clock: Clock
    ) -> None:
        """Use these providers, never the global ones; clock times iteration spans."""
        self._tracer_provider = tracer_provider
        self._tracer = tracer_provider.get_tracer(attr.TRACER_NAME)
        self._meter_provider = meter_provider
        self._clock = clock
        self._gauges: tuple[_Setter, _Setter, _Setter] | None = None
        if meter_provider is not None:
            meter = meter_provider.get_meter(attr.METER_NAME)
            self._gauges = (
                meter.create_gauge(attr.METRIC_COST_PER_TASK, unit="USD").set,
                meter.create_gauge(attr.METRIC_SUCCESS_RATE).set,
                meter.create_gauge(attr.METRIC_LATENCY_P95, unit="ms").set,
            )

    def record_task(self, run_id: str, result: TaskResult) -> None:
        """Emit one root span for the task and one child span per model call."""
        invocation = result.invocation
        start = result.started_at_ns
        root = self._tracer.start_span(
            attr.TASK_SPAN,
            context=Context(),
            start_time=start,
            attributes={
                attr.RUN_ID: run_id,
                attr.TASK_ID: result.request.task_id,
                attr.CONFIG_VERSION: result.config_version,
                attr.TASK_CATEGORY: result.difficulty.value,
                attr.SPLIT: result.request.split.value,
                attr.SUCCESS: attr.flag(result.success),
                attr.DATA_CACHE_HIT: attr.flag(result.request.data_cache_hit),
                attr.INFRA_SOURCE: result.infra_source.value,
                attr.COST_MODEL_USD: float(result.costs.model_usd),
                attr.COST_INFRA_USD: float(result.costs.infra_usd),
                attr.COST_DATA_USD: float(result.costs.data_usd),
            },
        )
        for call in invocation.calls:
            self._call_span(root, start, call)
        if invocation.error is not None:
            root.set_status(Status(StatusCode.ERROR, invocation.error))
        root.end(end_time=start + invocation.total_latency_ms * _NS_PER_MS)

    def record_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Emit one span per iteration with one child span per guardrail check."""
        span = self._tracer.start_span(
            attr.ITERATION_SPAN,
            context=Context(),
            start_time=self._clock.now_ns(),
            attributes={
                attr.RUN_ID: run_id,
                attr.ITERATION: record.iteration,
                attr.LEVER: record.proposal.lever.value,
                attr.DECISION: "approved" if record.decision.approved else "rejected",
                attr.ACCEPTED: attr.flag(record.accepted),
                attr.REASON: record.reason,
            },
        )
        context = trace.set_span_in_context(span)
        checks = record.guardrails.checks if record.guardrails is not None else ()
        for check in checks:
            child = self._tracer.start_span(
                attr.GUARDRAIL_SPAN_PREFIX + check.name,
                context=context,
                start_time=self._clock.now_ns(),
                attributes={
                    attr.CHECK_NAME: check.name,
                    attr.GUARDRAIL_PASSED: attr.flag(check.passed),
                },
            )
            code = StatusCode.OK if check.passed else StatusCode.ERROR
            child.set_status(Status(code, None if check.passed else check.detail))
            child.end(end_time=self._clock.now_ns())
        span.end(end_time=self._clock.now_ns())

    def record_summary(self, run_id: str, version: int, summary: RunSummary) -> None:
        """Record aggregate gauges labeled by run and config version, never by task."""
        if self._gauges is None:
            return
        set_cost, set_success, set_latency = self._gauges
        labels: Attributes = {
            attr.METRIC_LABEL_RUN_ID: run_id,
            attr.METRIC_LABEL_VERSION: version,
        }
        set_cost(float(summary.totals.total_usd / summary.n), labels)
        set_success(summary.success_rate, labels)
        set_latency(summary.p95_latency_ms, labels)

    def flush(self) -> None:
        """Force-flush spans and metrics so nothing is lost at exit."""
        self._tracer_provider.force_flush()
        if self._meter_provider is not None:
            self._meter_provider.force_flush()

    def _call_span(self, root: Span, task_start_ns: int, call: CallRecord) -> None:
        """Emit one model-call span under the task span."""
        start = task_start_ns + call.started_offset_ms * _NS_PER_MS
        span = self._tracer.start_span(
            f"{attr.GEN_AI_CHAT} {call.model}",
            context=trace.set_span_in_context(root),
            start_time=start,
            attributes={
                attr.GEN_AI_OPERATION: attr.GEN_AI_CHAT,
                attr.GEN_AI_REQUEST_MODEL: call.model,
                attr.GEN_AI_INPUT_TOKENS: call.input_tokens,
                attr.GEN_AI_OUTPUT_TOKENS: call.output_tokens,
                attr.MODEL_TIER: call.tier.value,
            },
        )
        span.end(end_time=start + call.latency_ms * _NS_PER_MS)
