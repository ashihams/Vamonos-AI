"""Keep a candidate only when it passes the guardrails and lowers cost per success."""

from decimal import Decimal

from costwise.domain.analysis import GroupStats, RunSummary
from costwise.domain.cost import CostBreakdown
from costwise.domain.guardrails import GuardrailPolicy
from costwise.domain.task import Split, TaskResult
from costwise.services.verdict import Standing, cost_per_success, judge
from tests.unit.domain.builders import ResultSpec, make_config, make_result, make_summary


def _summary(total_usd: str, successes: int) -> RunSummary:
    """Return a passing summary with this total cost and number of successes."""
    stats = GroupStats(n=successes, successes=successes, cost_usd=Decimal(total_usd))
    totals = CostBreakdown(model_usd=Decimal(total_usd), infra_usd=Decimal(0), data_usd=Decimal(0))
    return make_summary(1.0, 100).model_copy(
        update={"n": successes, "totals": totals, "by_difficulty": {"easy": stats}}
    )


def _policy(min_saving_pct: float) -> GuardrailPolicy:
    """Return the usual limits with this minimum saving."""
    return GuardrailPolicy(
        max_success_drop_pp=2.0,
        p95_multiplier=1.25,
        budget_stop_fraction=0.8,
        min_saving_pct=min_saving_pct,
    )


CURRENT = Standing(make_config(), _summary("0.40", 4), _summary("0.10", 1))


def _candidate(model_usd: str) -> list[TaskResult]:
    """Return one successful EVAL and HELDOUT task, each costing model_usd."""
    cost = Decimal(model_usd)
    spec = ResultSpec(model_usd=cost, infra_usd=Decimal(0), data_usd=Decimal(0))
    return [
        make_result(spec.model_copy(update={"task_id": "e"})),
        make_result(spec.model_copy(update={"task_id": "h", "split": Split.HELDOUT})),
    ]


def test_cost_per_success_spans_both_splits() -> None:
    """Total cost of both splits over their successes."""
    assert cost_per_success(CURRENT) == Decimal("0.1")


def test_a_cheaper_candidate_is_kept_with_its_saving() -> None:
    """0.10 to 0.05 per success is a 50% saving."""
    verdict = judge(_candidate("0.05"), make_config(), 2, CURRENT, _policy(1.0))
    assert verdict.accepted
    assert verdict.reason == "guardrails passed, cost per successful task -50.0%"


def test_an_equal_cost_candidate_is_rolled_back_even_with_no_minimum() -> None:
    """Passing the guardrails is not enough; the change must save something."""
    verdict = judge(_candidate("0.10"), make_config(), 2, CURRENT, _policy(0.0))
    assert not verdict.accepted
    assert verdict.reason == (
        "guardrails passed but no saving: cost per successful task 0.100000 -> 0.100000 USD;"
        " needs a drop"
    )
    assert verdict.guardrails is not None
    assert verdict.guardrails.passed


def test_a_saving_below_the_minimum_is_rolled_back() -> None:
    """0.5% is less than the 1% the policy asks for."""
    verdict = judge(_candidate("0.0995"), make_config(), 2, CURRENT, _policy(1.0))
    assert not verdict.accepted
    assert verdict.reason.endswith("needs at least a 1.0% drop")


def test_zero_cost_baseline_cannot_show_a_saving() -> None:
    """With nothing to save, the candidate is not kept."""
    free = Standing(make_config(), _summary("0", 4), _summary("0", 1))
    verdict = judge(_candidate("0"), make_config(), 2, free, _policy(0.0))
    assert not verdict.accepted
