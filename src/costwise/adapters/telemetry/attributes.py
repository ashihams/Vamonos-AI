"""Every telemetry attribute, span, and metric name; no other module may spell these out.

Canonical neatlogs keys come from the neatlogs Python SDK 1.4.26
(config/attribute-mapping.json): kinds are lowercase values of neatlogs.span.kind,
inputs and outputs are neatlogs.<kind>.input / .output, and session and end-user
identity belong on the trace root only. neatlogs only makes custom attributes
filterable when they start with neatlogs.workflow., neatlogs.session., or are
neatlogs.end_user.id.
"""

SPAN_KIND = "neatlogs.span.kind"
KIND_WORKFLOW = "workflow"
KIND_AGENT = "agent"
KIND_LLM = "llm"
KIND_TOOL = "tool"
KIND_GUARDRAIL = "guardrail"
KIND_EVALUATOR = "evaluator"

SESSION_ID = "neatlogs.session.id"
END_USER_ID = "neatlogs.end_user.id"
END_USER_METADATA = "neatlogs.end_user.metadata"

WORKFLOW_NAME = "neatlogs.workflow.name"
AGENT_NAME = "neatlogs.agent.name"
AGENT_ROLE = "neatlogs.agent.role"
TOOL_NAME = "neatlogs.tool.name"
TOOL_DESCRIPTION = "neatlogs.tool.description"

LLM_MODEL_NAME = "neatlogs.llm.model_name"
LLM_PROVIDER = "neatlogs.llm.provider"
LLM_PROMPT_TOKENS = "neatlogs.llm.token_count.prompt"
LLM_COMPLETION_TOKENS = "neatlogs.llm.token_count.completion"
LLM_TOTAL_TOKENS = "neatlogs.llm.token_count.total"
LLM_COST_USD = "neatlogs.llm.cost_usd"
LLM_PROVIDER_NAME = "litellm"

GUARDRAIL_NAME = "neatlogs.guardrail.name"
GUARDRAIL_PASSED = "neatlogs.guardrail.passed"
GUARDRAIL_REASON = "neatlogs.guardrail.reason"

_WORKFLOW = "neatlogs.workflow."

RUN_ID = _WORKFLOW + "run_id"
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

TASK_SPAN = "qualify_company"
DATA_SPAN = "fetch_company_data"
DATA_TOOL = "crustdata_company_enrich"
DATA_TOOL_DESCRIPTION = "Crustdata company enrich lookup, or the local cache"
SCORE_SPAN = "score_against_label"
ITERATION_SPAN = "optimizer_iteration"
OPTIMIZER_AGENT = "costwise_optimizer"
OPTIMIZER_ROLE = "Proposes one config change per iteration and keeps it only if it is safe"
APPROVAL_SPAN = "human_approval"
CANDIDATE_SPAN = "evaluate_candidate"
GUARDRAIL_SPAN_PREFIX = "guardrail "
LLM_SPAN_PREFIX = "chat "

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


def io_key(kind: str, direction: str) -> str:
    """Return the canonical input or output key for a span kind."""
    return f"neatlogs.{kind}.{direction}"


def flag(value: bool) -> str:
    """Return "true" or "false" for custom workflow filters, which neatlogs matches as strings."""
    return "true" if value else "false"
