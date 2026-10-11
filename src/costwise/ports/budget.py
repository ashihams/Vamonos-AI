"""Port for checking and recording model spend."""

from decimal import Decimal
from typing import Protocol

from costwise.ports.llm import TokenUsage


class BudgetGuard(Protocol):
    """Stops model calls once spend reaches the stop line."""

    def assert_can_spend(self) -> None:
        """Raise BudgetExceededError when spend has reached the stop line."""
        ...

    def record(self, model: str, usage: TokenUsage) -> Decimal:
        """Add the cost of one completed call and return that cost."""
        ...
