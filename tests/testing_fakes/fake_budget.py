"""Budget guard that records checks and charges."""

from decimal import Decimal

from costwise.domain.errors import BudgetExceededError
from costwise.ports.llm import TokenUsage


class RecordingBudget:
    """Allow calls until exhausted or past allowed_checks, recording every check and charge."""

    def __init__(self, exhausted: bool = False, allowed_checks: int | None = None) -> None:
        """Start with no checks or charges."""
        self.exhausted = exhausted
        self.allowed_checks = allowed_checks
        self.checks = 0
        self.charges: list[tuple[str, TokenUsage]] = []

    def assert_can_spend(self) -> None:
        """Count the check and raise when exhausted or over the allowed number of checks."""
        self.checks += 1
        over = self.allowed_checks is not None and self.checks > self.allowed_checks
        if self.exhausted or over:
            raise BudgetExceededError("budget exhausted")

    def record(self, model: str, usage: TokenUsage) -> Decimal:
        """Remember the charge and return a zero cost."""
        self.charges.append((model, usage))
        return Decimal(0)
