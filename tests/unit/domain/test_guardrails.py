"""Guardrail boundaries."""

import pytest

from costwise.domain.guardrails import (
    EVAL_SUCCESS,
    HELDOUT_SUCCESS,
    P95_LATENCY,
    GuardrailPolicy,
    evaluate_guardrails,
)
from tests.unit.domain.builders import make_summary

_POLICY = GuardrailPolicy(
    max_success_drop_pp=25.0,
    p95_multiplier=1.25,
    budget_stop_fraction=0.8,
)


def _passed(names: set[str], *, eval_rate: float, heldout_rate: float, p95: int) -> bool:
    """Evaluate one candidate against a 0.5 / 100ms baseline."""
    result = evaluate_guardrails(
        make_summary(0.5, 100),
        make_summary(eval_rate, p95),
        make_summary(heldout_rate, 100),
        make_summary(0.5, 100),
        _POLICY,
    )
    assert {check.name for check in result.checks} == {EVAL_SUCCESS, HELDOUT_SUCCESS, P95_LATENCY}
    assert all(check.detail for check in result.checks)
    failed = {check.name for check in result.checks if not check.passed}
    assert failed == names
    return result.passed


def test_guardrails_pass_exactly_at_each_threshold() -> None:
    """A candidate sitting on the success floor and the p95 limit passes."""
    assert _passed(set(), eval_rate=0.25, heldout_rate=0.25, p95=125) is True


def test_guardrails_pass_when_drop_allowance_is_zero_and_rates_match() -> None:
    """Zero allowed drop still passes an unchanged success rate."""
    policy = GuardrailPolicy(max_success_drop_pp=0.0, p95_multiplier=1.0, budget_stop_fraction=0.8)
    same = make_summary(0.5, 80)
    result = evaluate_guardrails(same, same, same, same, policy)
    assert result.passed is True


@pytest.mark.parametrize(
    ("eval_rate", "heldout_rate", "p95", "failed"),
    [
        (0.125, 0.25, 125, {EVAL_SUCCESS}),
        (0.25, 0.125, 125, {HELDOUT_SUCCESS}),
        (0.25, 0.25, 126, {P95_LATENCY}),
    ],
)
def test_guardrails_fail_one_check_past_the_boundary(
    eval_rate: float,
    heldout_rate: float,
    p95: int,
    failed: set[str],
) -> None:
    """Each check fails on its own when the candidate crosses that limit."""
    assert _passed(failed, eval_rate=eval_rate, heldout_rate=heldout_rate, p95=p95) is False
