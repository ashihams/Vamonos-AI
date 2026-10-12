"""Budget guard that records checks and charges."""

from decimal import Decimal

from costwise.domain.errors import BudgetExceededError
from costwise.ports.llm import TokenUsage


class RecordingBudget:
    """Allow calls until exhausted is set, and record every check and charge."""

    def __init__(self, exhausted: bool = False) -> None:
        """Start with no checks or charges."""
        self.exhausted = exhausted
        self.checks = 0
        self.charges: list[tuple[str, TokenUsage]] = []

    def assert_can_spend(self) -> None:
        """Count the check and raise when exhausted."""
        self.checks += 1
        if self.exhausted:
            raise BudgetExceededError("budget exhausted")

    def record(self, model: str, usage: TokenUsage) -> Decimal:
        """Remember the charge and return a zero cost."""
        self.charges.append((model, usage))
        return Decimal(0)
