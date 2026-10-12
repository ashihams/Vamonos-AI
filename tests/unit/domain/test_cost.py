"""Cost math."""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from costwise.domain.cost import (
    CostBreakdown,
    ModelPrice,
    PriceBook,
    breakdown,
    data_cost,
    infra_cost,
    model_cost,
)
from costwise.domain.errors import ConfigError
from costwise.domain.task import CallRecord, InvocationResult
from tests.unit.domain.builders import CallSpec, make_call, make_prices

_GB_SECOND = Decimal("0.0000166667")
_REQUEST = Decimal("0.0000002")


def _invocation(
    calls: tuple[CallRecord, ...],
    credits: Decimal,
    billed_ms: int | None,
    memory_mb: int | None,
) -> InvocationResult:
    """Build an invocation with the billing fields under test."""
    return InvocationResult(
        task_id="task-1",
        answer=None,
        calls=calls,
        data_credits=credits,
        total_latency_ms=10,
        error=None,
        billed_ms=billed_ms,
        memory_mb=memory_mb,
        cold_start=False,
    )


def test_model_cost_sums_token_prices() -> None:
    """Input and output tokens are priced per million and summed across calls."""
    calls = (
        make_call(CallSpec(model="cheap-model", input_tokens=1000, output_tokens=500)),
        make_call(CallSpec(model="strong-model", input_tokens=1_000_000, output_tokens=0)),
    )
    assert model_cost(calls, make_prices()) == Decimal("3.002")


def test_model_cost_of_no_calls_is_zero() -> None:
    """A task with no model calls has no model cost."""
    assert model_cost((), make_prices()) == Decimal(0)


def test_model_cost_rejects_unknown_model() -> None:
    """A call whose model is missing from the price book is a config error."""
    calls = (make_call(CallSpec(model="missing-model")),)
    with pytest.raises(ConfigError, match="unknown model price: missing-model"):
        model_cost(calls, make_prices())


@pytest.mark.parametrize(
    ("billed_ms", "memory_mb", "expected"),
    [
        (0, 1024, _REQUEST),
        (1000, 1024, _GB_SECOND + _REQUEST),
        (2000, 512, _GB_SECOND + _REQUEST),
        (1000, 2048, (_GB_SECOND * 2) + _REQUEST),
    ],
)
def test_infra_cost(billed_ms: int, memory_mb: int, expected: Decimal) -> None:
    """Lambda cost is billed GB-seconds times the price, plus the request fee."""
    assert infra_cost(billed_ms, memory_mb, make_prices()) == expected


@pytest.mark.parametrize(
    ("credits", "expected"),
    [
        (Decimal(0), Decimal(0)),
        (Decimal(2), Decimal("0.02")),
        (Decimal("1.5"), Decimal("0.015")),
    ],
)
def test_data_cost(credits: Decimal, expected: Decimal) -> None:
    """Data cost is credits times the credit price."""
    assert data_cost(credits, make_prices()) == expected


def test_total_usd_sums_components() -> None:
    """The total is the exact sum of the three components."""
    costs = CostBreakdown(
        model_usd=Decimal("1.25"), infra_usd=Decimal("0.25"), data_usd=Decimal("0.5")
    )
    assert costs.total_usd == Decimal("2")


@pytest.mark.parametrize(
    ("billed_ms", "memory_mb"),
    [
        (None, None),
        (1000, None),
        (None, 1024),
    ],
)
def test_breakdown_uses_zero_infra_without_billing(
    billed_ms: int | None, memory_mb: int | None
) -> None:
    """Missing billed time or memory yields zero infrastructure cost."""
    calls = (make_call(CallSpec(input_tokens=1000, output_tokens=500)),)
    invocation = _invocation(calls, Decimal(2), billed_ms, memory_mb)
    costs = breakdown(invocation, make_prices())
    assert costs.model_usd == Decimal("0.002")
    assert costs.infra_usd == Decimal(0)
    assert costs.data_usd == Decimal("0.02")


def test_breakdown_includes_infra_when_billing_is_present() -> None:
    """Present billing fields use the Lambda formula."""
    invocation = _invocation((), Decimal(0), 1000, 1024)
    costs = breakdown(invocation, make_prices())
    assert costs.infra_usd == _GB_SECOND + _REQUEST
    assert costs.total_usd == costs.infra_usd


def test_money_rejects_float() -> None:
    """Binary floats cannot enter a money field."""
    with pytest.raises(ValidationError):
        ModelPrice(input_per_1m_usd=0.1, output_per_1m_usd=Decimal(1))


@given(
    billed_ms=st.integers(min_value=0, max_value=1_000_000),
    memory_mb=st.integers(min_value=1, max_value=10_240),
    gb_second=st.decimals(
        min_value=Decimal(0),
        max_value=Decimal(1),
        places=6,
        allow_nan=False,
        allow_infinity=False,
    ),
    per_request=st.decimals(
        min_value=Decimal(0),
        max_value=Decimal(1),
        places=6,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(derandomize=True, max_examples=25)
def test_infra_cost_is_monotonic(
    billed_ms: int,
    memory_mb: int,
    gb_second: Decimal,
    per_request: Decimal,
) -> None:
    """Infrastructure cost does not fall when billed time or memory increases."""
    prices = PriceBook(
        models={},
        lambda_usd_per_gb_second=gb_second,
        lambda_usd_per_request=per_request,
        crustdata_usd_per_credit=Decimal(0),
    )
    base = infra_cost(billed_ms, memory_mb, prices)
    assert infra_cost(billed_ms + 1, memory_mb, prices) >= base
    assert infra_cost(billed_ms, memory_mb + 1, prices) >= base
