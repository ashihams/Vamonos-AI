"""Send one fake task trace and one iteration trace to neatlogs for a manual dashboard check.

Usage (NEATLOGS_API_KEY in the environment or .env):
    uv run python scripts/smoke_neatlogs.py

Then open the session named in the log line and check span kinds, inputs and outputs,
token counts, and the Passed/Blocked guardrails. The fake models are unpriced, so these
traces carry no cost; scripts/replay_neatlogs.py re-sends a real run with its costs.
"""

import logging
import sys
from decimal import Decimal

from costwise.adapters.system_clock import SystemClock
from costwise.adapters.telemetry.exporters import neatlogs_tracer_provider
from costwise.adapters.telemetry.otel_sink import OtelSink
from costwise.bootstrap import env_file
from costwise.domain.config import Lever
from costwise.domain.cost import CostBreakdown
from costwise.domain.guardrails import CheckOutcome, GuardrailResult
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.domain.task import (
    CallRecord,
    Difficulty,
    InfraCostSource,
    InvocationResult,
    ModelTier,
    QualificationAnswer,
    QualificationRequest,
    Split,
    TaskResult,
)
from costwise.logging_setup import configure_logging
from costwise.settings import NeatlogsSettings

_LOG = logging.getLogger("costwise.scripts.smoke_neatlogs")
_NS_PER_MS = 1_000_000


def smoke_task(started_at_ns: int) -> TaskResult:
    """Return a fake task with a cheap call that failed to parse and a strong retry."""
    calls = (
        CallRecord(
            model="smoke-cheap-model",
            tier=ModelTier.CHEAP,
            input_tokens=1200,
            output_tokens=40,
            latency_ms=300,
            started_offset_ms=5,
        ),
        CallRecord(
            model="smoke-strong-model",
            tier=ModelTier.STRONG,
            input_tokens=1200,
            output_tokens=60,
            latency_ms=900,
            started_offset_ms=320,
        ),
    )
    invocation = InvocationResult(
        task_id="smoke-task-0001",
        answer=QualificationAnswer(
            icp_fit=True, reasons=("smoke test",), headcount_band="201-500", stage="series_b"
        ),
        calls=calls,
        data_credits=Decimal(2),
        total_latency_ms=1250,
        error=None,
        billed_ms=1250,
        memory_mb=1024,
        cold_start=False,
    )
    return TaskResult(
        request=QualificationRequest(
            task_id="smoke-task-0001", domain="example.com", split=Split.EVAL, data_cache_hit=False
        ),
        config_version=1,
        difficulty=Difficulty.HARD,
        invocation=invocation,
        success=True,
        costs=CostBreakdown(
            model_usd=Decimal("0.0042"), infra_usd=Decimal("0.0000211"), data_usd=Decimal("0.02")
        ),
        infra_source=InfraCostSource.MODELED,
        started_at_ns=started_at_ns,
    )


def smoke_iteration() -> IterationRecord:
    """Return a fake rejected iteration with one passed and one failed guardrail."""
    return IterationRecord(
        iteration=1,
        proposal=Proposal(
            lever=Lever.ROUTING,
            new_value={"default_tier": "cheap"},
            rationale="smoke test",
            predicted_cost_change_pct=-30.0,
            risk="medium",
        ),
        decision=ApprovalDecision(approved=True, note="smoke test"),
        baseline_version=1,
        candidate_version=2,
        candidate_summary=None,
        guardrails=GuardrailResult(
            passed=False,
            checks=(
                CheckOutcome(name="eval_success", passed=True, detail="no drop"),
                CheckOutcome(name="heldout_success", passed=False, detail="smoke failure"),
            ),
        ),
        accepted=False,
        reason="smoke test rollback",
    )


def main() -> int:
    """Send the smoke traces, flush, and shut the provider down."""
    configure_logging()
    settings = NeatlogsSettings(_env_file=env_file())
    clock = SystemClock()
    provider = neatlogs_tracer_provider(settings.neatlogs_api_key)
    sink = OtelSink(provider, None, clock)
    run_id = f"smoke-{clock.now_ns() // _NS_PER_MS}"
    sink.record_task(run_id, smoke_task(clock.now_ns()))
    sink.record_iteration(run_id, smoke_iteration())
    sink.flush()
    provider.shutdown()
    _LOG.info("smoke traces sent run_id=%s", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
