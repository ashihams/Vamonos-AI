"""OpenTelemetry sink: task and iteration traces to neatlogs, metrics to a local Collector."""

from collections.abc import Callable

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util.types import Attributes

from costwise.adapters.telemetry import attributes as attr
from costwise.adapters.telemetry.iteration_spans import emit_iteration
from costwise.adapters.telemetry.task_spans import emit_task
from costwise.domain.analysis import RunSummary
from costwise.domain.cost import PriceBook
from costwise.domain.proposals import IterationRecord
from costwise.domain.task import TaskResult
from costwise.ports.clock import Clock

_Setter = Callable[[float, Attributes], None]


class OtelSink:
    """TelemetrySink over a dedicated TracerProvider and an optional MeterProvider."""

    def __init__(
        self,
        tracer_provider: TracerProvider,
        meter_provider: MeterProvider | None,
        clock: Clock,
        prices: PriceBook | None = None,
    ) -> None:
        """Use these providers, never the global ones; prices add a cost to each model call."""
        self._tracer_provider = tracer_provider
        self._tracer = tracer_provider.get_tracer(attr.TRACER_NAME)
        self._meter_provider = meter_provider
        self._clock = clock
        self._prices = prices
        self._gauges: tuple[_Setter, _Setter, _Setter] | None = None
        if meter_provider is not None:
            meter = meter_provider.get_meter(attr.METER_NAME)
            self._gauges = (
                meter.create_gauge(attr.METRIC_COST_PER_TASK, unit="USD").set,
                meter.create_gauge(attr.METRIC_SUCCESS_RATE).set,
                meter.create_gauge(attr.METRIC_LATENCY_P95, unit="ms").set,
            )

    def record_task(self, run_id: str, result: TaskResult) -> None:
        """Emit one trace for the task; all traces of a run share its session."""
        emit_task(self._tracer, run_id, result, self._prices)

    def record_iteration(self, run_id: str, record: IterationRecord) -> None:
        """Emit one trace for the optimizer iteration in the run's session."""
        emit_iteration(self._tracer, self._clock, run_id, record)

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
