"""Hard gates that decide whether a candidate run may replace the baseline."""

from costwise.domain.analysis import RunSummary
from costwise.domain.frozen import FrozenModel

_POINTS_PER_UNIT = 100.0
EVAL_SUCCESS = "eval_success"
HELDOUT_SUCCESS = "heldout_success"
P95_LATENCY = "p95_latency"


class GuardrailPolicy(FrozenModel):
    """Limits on success drop, latency, and how much of the budget may be spent."""

    max_success_drop_pp: float
    p95_multiplier: float
    budget_stop_fraction: float


class CheckOutcome(FrozenModel):
    """One named guardrail check."""

    name: str
    passed: bool
    detail: str


class GuardrailResult(FrozenModel):
    """Every guardrail check and whether they all passed."""

    passed: bool
    checks: tuple[CheckOutcome, ...]


def evaluate_guardrails(
    baseline: RunSummary,
    candidate: RunSummary,
    candidate_heldout: RunSummary,
    baseline_heldout: RunSummary,
    policy: GuardrailPolicy,
) -> GuardrailResult:
    """Compare eval success, held-out success, and candidate p95 with the baseline.

    ``success_rate`` is a fraction from 0 to 1. ``max_success_drop_pp`` is percentage
    points, so the allowed drop in rate units is that value divided by 100.
    A check at the exact limit passes.
    """
    checks = (
        _success_check(EVAL_SUCCESS, baseline, candidate, policy),
        _success_check(HELDOUT_SUCCESS, baseline_heldout, candidate_heldout, policy),
        _latency_check(baseline, candidate, policy),
    )
    return GuardrailResult(passed=all(check.passed for check in checks), checks=checks)


def _success_check(
    name: str,
    baseline: RunSummary,
    candidate: RunSummary,
    policy: GuardrailPolicy,
) -> CheckOutcome:
    """Return whether the candidate success rate stays within the allowed drop."""
    floor = baseline.success_rate - (policy.max_success_drop_pp / _POINTS_PER_UNIT)
    passed = candidate.success_rate >= floor
    detail = f"{name} candidate={candidate.success_rate} floor={floor}"
    return CheckOutcome(name=name, passed=passed, detail=detail)


def _latency_check(
    baseline: RunSummary,
    candidate: RunSummary,
    policy: GuardrailPolicy,
) -> CheckOutcome:
    """Return whether candidate p95 stays within the baseline multiple."""
    limit = baseline.p95_latency_ms * policy.p95_multiplier
    passed = candidate.p95_latency_ms <= limit
    detail = f"p95 candidate={candidate.p95_latency_ms} limit={limit}"
    return CheckOutcome(name=P95_LATENCY, passed=passed, detail=detail)
