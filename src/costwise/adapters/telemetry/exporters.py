"""OpenTelemetry providers for neatlogs traces and local Collector metrics."""

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import SecretStr

from costwise.adapters.telemetry import attributes as attr

_RESOURCE = Resource.create({attr.SERVICE_NAME_KEY: attr.SERVICE_NAME})


def neatlogs_tracer_provider(api_key: SecretStr) -> TracerProvider:
    """Return a dedicated provider exporting OTLP/gRPC over TLS with the x-api-key header."""
    exporter = OTLPSpanExporter(
        endpoint=attr.NEATLOGS_ENDPOINT,
        headers=((attr.NEATLOGS_KEY_HEADER, api_key.get_secret_value()),),
    )
    provider = TracerProvider(resource=_RESOURCE)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def collector_meter_provider(endpoint: str) -> MeterProvider:
    """Return a provider exporting metrics to a local Collector without TLS."""
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
    return MeterProvider(metric_readers=[reader], resource=_RESOURCE)
