"""Every telemetry attribute, span, and metric name; no other module may spell these out.

neatlogs only makes custom attributes filterable when they start with
neatlogs.workflow., neatlogs.session., or are neatlogs.end_user.id.
"""

_WORKFLOW = "neatlogs.workflow."

CONFIG_VERSION = _WORKFLOW + "config_version"
TASK_CATEGORY = _WORKFLOW + "task_category"
SUCCESS = _WORKFLOW + "success"
COST_MODEL_USD = _WORKFLOW + "cost_model_usd"
COST_INFRA_USD = _WORKFLOW + "cost_infra_usd"
COST_DATA_USD = _WORKFLOW + "cost_data_usd"
TASK_ID = _WORKFLOW + "task_id"
INFRA_SOURCE = _WORKFLOW + "infra_source"
SPLIT = _WORKFLOW + "split"
DATA_CACHE_HIT = _WORKFLOW + "data_cache_hit"
MODEL_TIER = _WORKFLOW + "model_tier"
ITERATION = _WORKFLOW + "iteration"
LEVER = _WORKFLOW + "lever"
DECISION = _WORKFLOW + "decision"
ACCEPTED = _WORKFLOW + "accepted"
REASON = _WORKFLOW + "reason"
CHECK_NAME = _WORKFLOW + "check_name"
RUN_ID = "neatlogs.session.run_id"

# TODO(VERIFY: neatlogs renders neatlogs.guardrail.passed on plain OTLP spans as Passed/Blocked)
GUARDRAIL_PASSED = "neatlogs.guardrail.passed"

GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_OPERATION = "gen_ai.operation.name"
GEN_AI_CHAT = "chat"

TASK_SPAN = "qualify_company"
ITERATION_SPAN = "optimizer_iteration"
GUARDRAIL_SPAN_PREFIX = "guardrail "

SERVICE_NAME_KEY = "service.name"
SERVICE_NAME = "costwise"
METER_NAME = "costwise"
TRACER_NAME = "costwise"
METRIC_COST_PER_TASK = "costwise.cost_per_task_usd"
METRIC_SUCCESS_RATE = "costwise.success_rate"
METRIC_LATENCY_P95 = "costwise.latency_p95_ms"
METRIC_LABEL_RUN_ID = "run_id"
METRIC_LABEL_VERSION = "config_version"

NEATLOGS_ENDPOINT = "ingest.neatlogs.com:443"
NEATLOGS_KEY_HEADER = "x-api-key"


def flag(value: bool) -> str:
    """Return "true" or "false"; neatlogs filters these as strings."""
    return "true" if value else "false"
