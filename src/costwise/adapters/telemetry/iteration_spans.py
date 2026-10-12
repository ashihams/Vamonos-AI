"""One neatlogs trace per optimizer iteration: approval, candidate evaluation, guardrails."""

import json

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue

from costwise.adapters.telemetry import attributes as attr
from costwise.domain.analysis import RunSummary
from costwise.domain.guardrails import CheckOutcome
from costwise.domain.proposals import IterationRecord
from costwise.ports.clock import Clock


def emit_iteration(tracer: Tracer, clock: Clock, run_id: str, record: IterationRecord) -> None:
    """Emit an AGENT root with an approval GUARDRAIL, an EVALUATOR, and a GUARDRAIL per check."""
    root = tracer.start_span(
        attr.ITERATION_SPAN,
        context=Context(),
        start_time=clock.now_ns(),
        attributes=_root_attributes(run_id, record),
    )
    context = trace.set_span_in_context(root)
    _gate(tracer, clock, context, _approval(record))
    if record.candidate_summary is not None:
        _candidate_span(tracer, clock, context, record, record.candidate_summary)
    checks = record.guardrails.checks if record.guardrails is not None else ()
    for check in checks:
        _gate(tracer, clock, context, check)
    root.end(end_time=clock.now_ns())


def _root_attributes(run_id: str, record: IterationRecord) -> dict[str, AttributeValue]:
    """Return identity, the proposal as input, the decision as output, and workflow filters."""
    proposal = record.proposal
    outcome = {
        "accepted": record.accepted,
        "reason": record.reason,
        "candidate_version": record.candidate_version,
    }
    return {
        attr.SPAN_KIND: attr.KIND_AGENT,
        attr.AGENT_NAME: attr.OPTIMIZER_AGENT,
        attr.AGENT_ROLE: attr.OPTIMIZER_ROLE,
        attr.SESSION_ID: run_id,
        attr.io_key(attr.KIND_AGENT, "input"): proposal.model_dump_json(),
        attr.io_key(attr.KIND_AGENT, "output"): json.dumps(outcome),
        attr.RUN_ID: run_id,
        attr.ITERATION: record.iteration,
        attr.LEVER: proposal.lever.value,
        attr.DECISION: "approved" if record.decision.approved else "rejected",
        attr.ACCEPTED: attr.flag(record.accepted),
        attr.REASON: record.reason,
    }


def _approval(record: IterationRecord) -> CheckOutcome:
    """Return the human decision as a check, so neatlogs shows it as Passed or Blocked."""
    note = record.decision.note or ("approved" if record.decision.approved else "declined")
    return CheckOutcome(name=attr.APPROVAL_SPAN, passed=record.decision.approved, detail=note)


def _gate(tracer: Tracer, clock: Clock, context: Context, check: CheckOutcome) -> None:
    """Emit one GUARDRAIL span; a failed check carries an ERROR status and its reason."""
    name = (
        check.name if check.name == attr.APPROVAL_SPAN else attr.GUARDRAIL_SPAN_PREFIX + check.name
    )
    attributes: dict[str, AttributeValue] = {
        attr.SPAN_KIND: attr.KIND_GUARDRAIL,
        attr.GUARDRAIL_NAME: check.name,
        attr.GUARDRAIL_PASSED: check.passed,
        attr.io_key(attr.KIND_GUARDRAIL, "output"): check.detail,
    }
    if not check.passed:
        attributes[attr.GUARDRAIL_REASON] = check.detail
    span = tracer.start_span(
        name, context=context, start_time=clock.now_ns(), attributes=attributes
    )
    code = StatusCode.OK if check.passed else StatusCode.ERROR
    span.set_status(Status(code, None if check.passed else check.detail))
    span.end(end_time=clock.now_ns())


def _candidate_span(
    tracer: Tracer, clock: Clock, context: Context, record: IterationRecord, summary: RunSummary
) -> None:
    """Emit the candidate run's headline numbers as an EVALUATOR span."""
    numbers = {
        "tasks": summary.n,
        "success_rate": summary.success_rate,
        "cost_per_successful_task_usd": str(summary.cost_per_successful_task),
        "total_usd": str(summary.totals.total_usd),
        "p95_latency_ms": summary.p95_latency_ms,
    }
    span = tracer.start_span(
        attr.CANDIDATE_SPAN,
        context=context,
        start_time=clock.now_ns(),
        attributes={
            attr.SPAN_KIND: attr.KIND_EVALUATOR,
            attr.io_key(attr.KIND_EVALUATOR, "input"): f"config v{record.candidate_version}",
            attr.io_key(attr.KIND_EVALUATOR, "output"): json.dumps(numbers),
        },
    )
    span.end(end_time=clock.now_ns())
