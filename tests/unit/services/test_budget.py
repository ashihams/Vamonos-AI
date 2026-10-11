"""Budget tracking, the stop line, and concurrent recording."""

import threading
from decimal import Decimal

import pytest

from costwise.domain.errors import BudgetExceededError, ConfigError
from costwise.ports.llm import TokenUsage
from costwise.services.budget import BudgetService
from tests.unit.domain.builders import make_prices

_MILLION_IN = TokenUsage(input_tokens=1_000_000, output_tokens=0)


def test_record_costs_calls_and_stops_at_the_fraction() -> None:
    """Costs use the price book; spend at the stop line refuses further calls."""
    budget = BudgetService(Decimal("2"), 0.5, make_prices())
    budget.assert_can_spend()
    assert budget.record(
        "cheap-model", TokenUsage(input_tokens=1000, output_tokens=500)
    ) == Decimal("0.002")
    assert budget.remaining() == Decimal("1.998")
    budget.record("cheap-model", TokenUsage(input_tokens=998_000, output_tokens=0))
    assert budget.spent() == Decimal("1.000")
    with pytest.raises(BudgetExceededError, match="stop line"):
        budget.assert_can_spend()


def test_unknown_model_and_bad_settings_raise_config_errors() -> None:
    """A model without a price and an invalid cap or fraction are configuration errors."""
    with pytest.raises(ConfigError, match="unknown model price"):
        BudgetService(Decimal("1"), 0.8, make_prices()).record("missing", _MILLION_IN)
    for cap, fraction in [(Decimal(0), 0.8), (Decimal(1), 0.0), (Decimal(1), 1.5)]:
        with pytest.raises(ConfigError, match="budget needs"):
            BudgetService(cap, fraction, make_prices())


def test_concurrent_records_are_not_lost() -> None:
    """Many threads recording at once sum exactly, and the stop line then holds."""
    budget = BudgetService(Decimal("10"), 0.8, make_prices())
    usage = TokenUsage(input_tokens=1000, output_tokens=0)
    start = threading.Barrier(8)

    def worker() -> None:
        """Record 250 small calls after every thread is ready."""
        start.wait()
        for _ in range(250):
            budget.record("cheap-model", usage)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert budget.spent() == Decimal("2.000")

    for _ in range(6):
        budget.record("cheap-model", _MILLION_IN)
    with pytest.raises(BudgetExceededError):
        budget.assert_can_spend()


def test_concurrent_callers_stop_once_the_line_is_crossed() -> None:
    """Threads that check before each call stop shortly after the stop line."""
    budget = BudgetService(Decimal("1"), 0.5, make_prices())
    usage = TokenUsage(input_tokens=10_000, output_tokens=0)
    calls: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        """Call until the budget refuses."""
        while True:
            try:
                budget.assert_can_spend()
            except BudgetExceededError:
                return
            budget.record("cheap-model", usage)
            with lock:
                calls.append(1)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert budget.spent() >= Decimal("0.5")
    assert budget.spent() < Decimal("0.5") + Decimal("0.01") * 4
    assert len(calls) == int(budget.spent() / Decimal("0.01"))
