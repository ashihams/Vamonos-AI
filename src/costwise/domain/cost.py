"""Price book and exact Decimal cost math."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import BeforeValidator

from costwise.domain.errors import ConfigError
from costwise.domain.frozen import FrozenModel

if TYPE_CHECKING:
    from costwise.domain.task import CallRecord, InvocationResult

_MS_PER_SECOND = 1000
_MB_PER_GB = 1024


def _reject_float_money(value: object) -> object:
    """Reject binary floats so money stays exact."""
    if isinstance(value, float):
        raise ValueError("money must be Decimal, not float")
    return value


Money = Annotated[Decimal, BeforeValidator(_reject_float_money)]


class ModelPrice(FrozenModel):
    """USD price for one million input tokens and one million output tokens."""

    input_per_1m_usd: Money
    output_per_1m_usd: Money


class PriceBook(FrozenModel):
    """Prices for models, Lambda, and company-data credits."""

    models: dict[str, ModelPrice]
    lambda_usd_per_gb_second: Money
    lambda_usd_per_request: Money
    crustdata_usd_per_credit: Money


class CostBreakdown(FrozenModel):
    """Model, infrastructure, and data cost for one task or a whole run."""

    model_usd: Money
    infra_usd: Money
    data_usd: Money

    @property
    def total_usd(self) -> Decimal:
        """Return the sum of the three cost components."""
        return self.model_usd + self.infra_usd + self.data_usd


def model_cost(calls: Sequence[CallRecord], prices: PriceBook) -> Decimal:
    """Return token cost for the calls using the price book."""
    total = Decimal(0)
    for call in calls:
        total += usage_cost(call.model, call.input_tokens, call.output_tokens, prices)
    return total


def usage_cost(model: str, input_tokens: int, output_tokens: int, prices: PriceBook) -> Decimal:
    """Return the token cost of one call to the named model."""
    try:
        price = prices.models[model]
    except KeyError as exc:
        raise ConfigError(f"unknown model price: {model}") from exc
    return _token_cost(input_tokens, price.input_per_1m_usd) + _token_cost(
        output_tokens, price.output_per_1m_usd
    )


def infra_cost(billed_ms: int, memory_mb: int, prices: PriceBook) -> Decimal:
    """Return Lambda cost from billed milliseconds and memory."""
    billed_seconds = Decimal(billed_ms) / Decimal(_MS_PER_SECOND)
    memory_gb = Decimal(memory_mb) / Decimal(_MB_PER_GB)
    gb_seconds = billed_seconds * memory_gb
    return gb_seconds * prices.lambda_usd_per_gb_second + prices.lambda_usd_per_request


def data_cost(credits: Decimal, prices: PriceBook) -> Decimal:
    """Return credit cost from the price book."""
    return credits * prices.crustdata_usd_per_credit


def breakdown(invocation: InvocationResult, prices: PriceBook) -> CostBreakdown:
    """Return component costs. Infrastructure is zero when billing fields are absent."""
    if invocation.billed_ms is None or invocation.memory_mb is None:
        infra = Decimal(0)
    else:
        infra = infra_cost(invocation.billed_ms, invocation.memory_mb, prices)
    return CostBreakdown(
        model_usd=model_cost(invocation.calls, prices),
        infra_usd=infra,
        data_usd=data_cost(invocation.data_credits, prices),
    )


def _token_cost(tokens: int, usd_per_million: Decimal) -> Decimal:
    """Return the cost of one token count at a per-million price."""
    return Decimal(tokens) / Decimal(1_000_000) * usd_per_million
