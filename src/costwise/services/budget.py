"""Thread-safe model spend tracking against a capped budget."""

import threading
from decimal import Decimal

from costwise.domain.cost import PriceBook, usage_cost
from costwise.domain.errors import BudgetExceededError, ConfigError
from costwise.ports.llm import TokenUsage


class BudgetService:
    """Tracks spend and refuses new calls at stop_fraction of the cap.

    The check and the record are separate steps, so calls already in flight
    when the stop line is crossed still complete and are recorded.
    """

    def __init__(self, cap_usd: Decimal, stop_fraction: float, prices: PriceBook) -> None:
        """Set the cap, the fraction at which calls stop, and the prices used to cost calls."""
        if cap_usd <= 0 or not 0.0 < stop_fraction <= 1.0:
            raise ConfigError("budget needs cap_usd > 0 and 0 < stop_fraction <= 1")
        self._cap = cap_usd
        self._stop_at = cap_usd * Decimal(str(stop_fraction))
        self._prices = prices
        self._spent = Decimal(0)
        self._lock = threading.Lock()

    def record(self, model: str, usage: TokenUsage) -> Decimal:
        """Add the cost of one completed call and return that cost."""
        cost = usage_cost(model, usage.input_tokens, usage.output_tokens, self._prices)
        with self._lock:
            self._spent += cost
        return cost

    def spent(self) -> Decimal:
        """Return the total recorded spend."""
        with self._lock:
            return self._spent

    def remaining(self) -> Decimal:
        """Return the cap minus recorded spend; negative after an overshoot."""
        with self._lock:
            return self._cap - self._spent

    def assert_can_spend(self) -> None:
        """Raise BudgetExceededError once spend reaches the stop line."""
        with self._lock:
            spent = self._spent
        if spent >= self._stop_at:
            raise BudgetExceededError(
                f"model spend {spent} reached the stop line {self._stop_at} of cap {self._cap}"
            )
