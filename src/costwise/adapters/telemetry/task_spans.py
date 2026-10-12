"""One neatlogs trace per task: data lookup, model calls, and the label score.

Spans are built driver-side from the returned result with explicit timestamps,
so a remote runner never exports anything itself. The data-lookup span covers
the time before the first model call, which also includes building the payload.
"""

import json

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue

from costwise.adapters.telemetry import attributes as attr
from costwise.domain.cost import PriceBook, usage_cost
from costwise.domain.task import CallRecord, TaskResult

NS_PER_MS = 1_000_000


def emit_task(tracer: Tracer, run_id: str, result: TaskResult, prices: PriceBook | None) -> None:
    """Emit the task trace: a workflow root with tool, LLM, and evaluator children."""
    invocation = result.invocation
    start = result.started_at_ns
    end = start + invocation.total_latency_ms * NS_PER_MS
    root = tracer.start_span(
        attr.TASK_SPAN,
        context=Context(),
        start_time=start,
        attributes=_root_attributes(run_id, result),
    )
    context = trace.set_span_in_context(root)
    _data_span(tracer, context, result)
    last = len(invocation.calls) - 1
    for index, call in enumerate(invocation.calls):
        span = _call_span(tracer, context, start, call, prices)
        if index == last and invocation.answer is not None:
            span.set_attribute(attr.io_key(attr.KIND_LLM, "output"), _answer_json(result))
        span.end(end_time=start + (call.started_offset_ms + call.latency_ms) * NS_PER_MS)
    _score_span(tracer, context, result, end)
    if invocation.error is not None:
        root.set_status(Status(StatusCode.ERROR, invocation.error))
    root.end(end_time=end)


def _root_attributes(run_id: str, result: TaskResult) -> dict[str, AttributeValue]:
    """Return identity, input, output, and the filterable workflow fields of a task."""
    request = result.request
    task_input = {
        "task_id": request.task_id,
        "domain": request.domain,
        "split": request.split.value,
        "config_version": result.config_version,
    }
    output = _answer_json(result) if result.invocation.answer else _error_json(result)
    end_user = {"split": request.split.value, "difficulty": result.difficulty.value}
    return {
        attr.SPAN_KIND: attr.KIND_WORKFLOW,
        attr.WORKFLOW_NAME: attr.TASK_SPAN,
        attr.SESSION_ID: run_id,
        attr.END_USER_ID: request.domain,
        attr.END_USER_METADATA: json.dumps(end_user),
        attr.io_key(attr.KIND_WORKFLOW, "input"): json.dumps(task_input),
        attr.io_key(attr.KIND_WORKFLOW, "output"): output,
        attr.RUN_ID: run_id,
        attr.TASK_ID: request.task_id,
        attr.CONFIG_VERSION: result.config_version,
        attr.TASK_CATEGORY: result.difficulty.value,
        attr.SPLIT: request.split.value,
        attr.SUCCESS: attr.flag(result.success),
        attr.DATA_CACHE_HIT: attr.flag(request.data_cache_hit),
        attr.INFRA_SOURCE: result.infra_source.value,
        attr.COST_MODEL_USD: float(result.costs.model_usd),
        attr.COST_INFRA_USD: float(result.costs.infra_usd),
        attr.COST_DATA_USD: float(result.costs.data_usd),
    }


def _data_span(tracer: Tracer, context: Context, result: TaskResult) -> None:
    """Emit the company-data lookup as a TOOL span ending at the first model call."""
    invocation = result.invocation
    calls = invocation.calls
    offset_ms = calls[0].started_offset_ms if calls else invocation.total_latency_ms
    lookup = {
        "cache_hit": result.request.data_cache_hit,
        "credits": str(invocation.data_credits),
        "data_usd": str(result.costs.data_usd),
    }
    span = tracer.start_span(
        attr.DATA_SPAN,
        context=context,
        start_time=result.started_at_ns,
        attributes={
            attr.SPAN_KIND: attr.KIND_TOOL,
            attr.TOOL_NAME: attr.DATA_TOOL,
            attr.TOOL_DESCRIPTION: attr.DATA_TOOL_DESCRIPTION,
            attr.io_key(attr.KIND_TOOL, "input"): result.request.domain,
            attr.io_key(attr.KIND_TOOL, "output"): json.dumps(lookup),
        },
    )
    if not calls and invocation.error is not None:
        span.set_status(Status(StatusCode.ERROR, invocation.error))
    span.end(end_time=result.started_at_ns + offset_ms * NS_PER_MS)


def _call_span(
    tracer: Tracer, context: Context, task_start_ns: int, call: CallRecord, prices: PriceBook | None
) -> Span:
    """Start one LLM span with model, provider, token counts, and cost when prices are known."""
    attributes: dict[str, AttributeValue] = {
        attr.SPAN_KIND: attr.KIND_LLM,
        attr.LLM_MODEL_NAME: call.model,
        attr.LLM_PROVIDER: attr.LLM_PROVIDER_NAME,
        attr.LLM_PROMPT_TOKENS: call.input_tokens,
        attr.LLM_COMPLETION_TOKENS: call.output_tokens,
        attr.LLM_TOTAL_TOKENS: call.input_tokens + call.output_tokens,
        attr.MODEL_TIER: call.tier.value,
    }
    if prices is not None and call.model in prices.models:
        cost = usage_cost(call.model, call.input_tokens, call.output_tokens, prices)
        attributes[attr.LLM_COST_USD] = float(cost)
    return tracer.start_span(
        attr.LLM_SPAN_PREFIX + call.model,
        context=context,
        start_time=task_start_ns + call.started_offset_ms * NS_PER_MS,
        attributes=attributes,
    )


def _score_span(tracer: Tracer, context: Context, result: TaskResult, at_ns: int) -> None:
    """Emit the comparison with the stored label as an EVALUATOR span at the end of the task."""
    verdict = {"success": result.success, "difficulty": result.difficulty.value}
    span = tracer.start_span(
        attr.SCORE_SPAN,
        context=context,
        start_time=at_ns,
        attributes={
            attr.SPAN_KIND: attr.KIND_EVALUATOR,
            attr.io_key(attr.KIND_EVALUATOR, "input"): result.request.task_id,
            attr.io_key(attr.KIND_EVALUATOR, "output"): json.dumps(verdict),
        },
    )
    span.end(end_time=at_ns)


def _answer_json(result: TaskResult) -> str:
    """Return the parsed answer as JSON."""
    answer = result.invocation.answer
    return "" if answer is None else answer.model_dump_json()


def _error_json(result: TaskResult) -> str:
    """Return the invocation error as JSON."""
    return json.dumps({"error": result.invocation.error})
