"""Run summaries."""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from costwise.domain.analysis import summarize
from costwise.domain.errors import CostwiseError
from costwise.domain.task import Difficulty, ModelTier, TaskResult
from tests.unit.domain.builders import CallSpec, ResultSpec, make_call, make_result


def _money() -> st.SearchStrategy[Decimal]:
    """Draw a small non-negative money amount."""
    return st.decimals(
        min_value=Decimal(0),
        max_value=Decimal(3),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )


def test_summarize_rejects_zero_successes() -> None:
    """A run with no successful tasks cannot price a successful task."""
    failed = make_result(ResultSpec(success=False))
    with pytest.raises(CostwiseError, match="no successful tasks"):
        summarize(())
    with pytest.raises(CostwiseError, match="no successful tasks"):
        summarize((failed,))


def test_percentiles_use_nearest_rank() -> None:
    """p50 and p95 pick the nearest-rank sample from task latency."""
    latencies = (10, 20, 30, 40)
    results = tuple(
        make_result(ResultSpec(task_id=f"t{latency}", total_latency_ms=latency))
        for latency in latencies
    )
    summary = summarize(results)
    assert summary.p50_latency_ms == 20
    assert summary.p95_latency_ms == 40
    five = tuple(
        make_result(ResultSpec(task_id=f"n{latency}", total_latency_ms=latency))
        for latency in (10, 20, 30, 40, 50)
    )
    wider = summarize(five)
    assert wider.p50_latency_ms == 30
    assert wider.p95_latency_ms == 50


def test_cold_starts_are_left_out_of_latency_percentiles() -> None:
    """A slow cold start does not set p95 unless asked to, or unless every task was cold."""
    warm = make_result(ResultSpec(task_id="warm", total_latency_ms=100))
    cold = make_result(ResultSpec(task_id="cold", total_latency_ms=900, cold_start=True))
    assert summarize((warm, cold)).p95_latency_ms == 100
    assert summarize((warm, cold), exclude_cold_start=False).p95_latency_ms == 900
    assert summarize((cold,)).p95_latency_ms == 900


def test_summary_rates_costs_and_groups() -> None:
    """Rates, component totals, and difficulty groups follow the task list."""
    hit = make_result(
        ResultSpec(
            task_id="hit",
            data_cache_hit=True,
            difficulty=Difficulty.HARD,
            success=False,
            model_usd=Decimal("1"),
            infra_usd=Decimal("2"),
            data_usd=Decimal("3"),
            calls=(make_call(CallSpec(tier=ModelTier.CHEAP)),),
        )
    )
    miss = make_result(
        ResultSpec(
            task_id="miss",
            difficulty=Difficulty.EASY,
            success=True,
            model_usd=Decimal("4"),
            infra_usd=Decimal("5"),
            data_usd=Decimal("6"),
            calls=(make_call(CallSpec(tier=ModelTier.STRONG)),),
        )
    )
    summary = summarize((hit, miss))
    assert summary.n == 2
    assert summary.success_rate == 0.5
    assert summary.cache_hit_rate == 0.5
    assert summary.repeat_rate == 0.5
    assert summary.totals.model_usd == Decimal("5")
    assert summary.totals.infra_usd == Decimal("7")
    assert summary.totals.data_usd == Decimal("9")
    assert summary.totals.total_usd == Decimal("21")
    assert summary.cost_per_successful_task == Decimal("21")
    assert summary.by_difficulty["hard"].n == 1
    assert summary.by_difficulty["hard"].successes == 0
    assert summary.by_difficulty["hard"].cost_usd == Decimal("6")
    assert summary.by_difficulty["easy"].successes == 1
    assert summary.easy_routed_strong == 1
    assert summary.hard_routed_cheap_failed == 1
    assert set(summary.by_tier) == {"cheap", "strong"}


def test_repeat_rate_counts_domains_seen_earlier() -> None:
    """Of a, b, a, a, two tasks repeat an earlier domain."""
    results = [
        make_result(ResultSpec(task_id=f"t{i}", domain=domain))
        for i, domain in enumerate(
            ["a.example.com", "b.example.com", "a.example.com", "a.example.com"]
        )
    ]
    assert summarize(results).repeat_rate == 0.5


def test_token_average_sums_calls_then_averages_tasks() -> None:
    """Each task contributes the sum of its calls, including a retry."""
    first = make_result(
        ResultSpec(
            task_id="first",
            calls=(
                make_call(CallSpec(input_tokens=100, output_tokens=20)),
                make_call(CallSpec(input_tokens=300, output_tokens=10, tier=ModelTier.STRONG)),
            ),
        )
    )
    second = make_result(
        ResultSpec(
            task_id="second",
            calls=(make_call(CallSpec(input_tokens=200, output_tokens=40)),),
        )
    )
    summary = summarize((first, second))
    assert summary.avg_input_tokens == 300
    assert summary.avg_output_tokens == 35
    assert summary.easy_routed_strong == 0


def test_failed_hard_cheap_ignores_later_calls_and_successes() -> None:
    """Only the first call's tier counts, and a success is not a cheap failure."""
    retry = make_result(
        ResultSpec(
            task_id="retry",
            difficulty=Difficulty.HARD,
            success=False,
            calls=(
                make_call(CallSpec(tier=ModelTier.CHEAP)),
                make_call(CallSpec(tier=ModelTier.STRONG)),
            ),
        )
    )
    succeeded = make_result(
        ResultSpec(
            task_id="ok",
            difficulty=Difficulty.HARD,
            success=True,
            calls=(make_call(CallSpec(tier=ModelTier.CHEAP)),),
        )
    )
    strong_fail = make_result(
        ResultSpec(
            task_id="strong",
            difficulty=Difficulty.HARD,
            success=False,
            calls=(make_call(CallSpec(tier=ModelTier.STRONG)),),
        )
    )
    summary = summarize((retry, succeeded, strong_fail))
    assert summary.hard_routed_cheap_failed == 1


def test_tasks_without_calls_are_omitted_from_tiers() -> None:
    """A task that never called a model does not appear in the tier groups."""
    silent = make_result(ResultSpec(task_id="silent", calls=(), success=True))
    spoken = make_result(ResultSpec(task_id="spoken", success=True))
    summary = summarize((silent, spoken))
    assert summary.by_tier.keys() == {"cheap"}
    assert summary.avg_input_tokens == 50
    assert summary.by_difficulty["easy"].n == 2
    assert summary.by_difficulty["hard"].n == 0


@given(data=st.data())
@settings(derandomize=True, max_examples=20)
def test_summary_components_sum_to_total(data: st.DataObject) -> None:
    """Component totals add up, and they add up to the tasks that produced them."""
    count = data.draw(st.integers(min_value=1, max_value=4))
    money = _money()
    results: list[TaskResult] = []
    for index in range(count):
        success = not index or data.draw(st.booleans())
        results.append(
            make_result(
                ResultSpec(
                    task_id=f"t{index}",
                    success=success,
                    model_usd=data.draw(money),
                    infra_usd=data.draw(money),
                    data_usd=data.draw(money),
                )
            )
        )
    summary = summarize(results)
    assert summary.totals.total_usd == (
        summary.totals.model_usd + summary.totals.infra_usd + summary.totals.data_usd
    )
    assert summary.totals.model_usd == sum((item.costs.model_usd for item in results), Decimal(0))
    assert summary.totals.infra_usd == sum((item.costs.infra_usd for item in results), Decimal(0))
    assert summary.totals.data_usd == sum((item.costs.data_usd for item in results), Decimal(0))
