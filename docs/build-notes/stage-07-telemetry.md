Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 7 had to deliver

`docs/SPEC.md` asks for driver-side OpenTelemetry spans to neatlogs, summary gauges to a local Collector only, attribute names in one module, collector config, and `scripts/smoke_neatlogs.py`. The stage is STOP AND ASK: confirm the neatlogs key, run the smoke script, and report what the dashboard shows. Export is OTLP/gRPC with TLS at `ingest.neatlogs.com:443` and the `x-api-key` header, as the spec says neatlogs engineers confirmed.

## Human decisions

Cursor built the code and the in-memory tests first, then stopped. The question was whether to run the smoke script now, open the pull request and check the dashboard later, or leave the stage uncommitted. `hackathon.md` records the builder's choice as committing before the dashboard check. Nothing was sent to neatlogs. The smoke check needed the neatlogs key, which was not claimed yet.

## How it was built

`OtelSink` builds spans on the driver from returned results, with explicit timestamps. Each task gets one root span with run, task, config version, category, split, success, cache hit, infra source, and the three cost components. Each model call gets a nested child span with `gen_ai.*` model and token attributes. An optimizer iteration is one span with lever, decision, accepted, and reason, plus one child span per guardrail check with an OK or ERROR status. Summary gauges (cost per task, success rate, p95 latency) are labeled by run and config version, never task id. They go only to a local Collector, when one is configured. Without `NEATLOGS_API_KEY`, telemetry is a no-op. A dedicated tracer provider is used, not the global one. All attribute names live in `attributes.py`, and a test fails if another module spells one out.

Commit `c7018a9` on `feat/telemetry`, 19 files. New files include `attributes.py`, `otel_sink.py`, `exporters.py`, `scripts/smoke_neatlogs.py`, `infra/collector/config.yaml`, `docker-compose.yaml`, `tests/contract/test_otel_sink.py`, and `tests/unit/adapters/test_telemetry_names.py`. The end-to-end CLI test clears any real neatlogs key so tests never send traces. The Collector output folder is gitignored.

`make check` exited 0. pytest: 237 passed. Overall coverage 99.77%. Domain and services 100%. Span tree, timestamps, attributes, statuses, and gauge labels are checked with the OpenTelemetry in-memory exporter and reader. The only uncovered lines called out in the chat are the Collector metrics exporter, left untested so a test would not reach a real Collector.

PR #8 is open against `feat/eval-baseline`: https://github.com/ashihams/Vamonos-AI/pull/8. The PR description says the dashboard check is pending.

## What did not work

The smoke script was not run. There was no key, and the stage stopped at the ask. A meter provider pointed at a real Collector was not constructed in tests, because shutdown might retry gRPC against a server that is not there.

## Left open

`TODO(VERIFY: neatlogs renders neatlogs.guardrail.passed on plain OTLP spans as Passed/Blocked)`. The span status is also set to OK or ERROR. The dashboard checks (token fields, filterable `neatlogs.workflow.*` attributes, span nesting, guardrail rendering) were open. The Collector image is `otel/opentelemetry-collector-contrib:latest`, unpinned, and the file write was untested. If export hangs with `DEADLINE_EXCEEDED`, the spec says to set `GRPC_DNS_RESOLVER=native`. That was not hit, because the script was not run.
