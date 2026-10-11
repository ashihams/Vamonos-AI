"""Retry and budget wrappers around an LLMClient."""

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.wait import wait_base

from costwise.domain.errors import TransientLLMError
from costwise.ports.budget import BudgetGuard
from costwise.ports.llm import LLMClient, LLMRequest, LLMResponse

_ATTEMPTS = 3


class RetryingLLMClient:
    """Retry up to twice on rate limits, server errors, and timeouts."""

    def __init__(self, inner: LLMClient, wait: wait_base | None = None) -> None:
        """Wrap inner; wait controls the pause between attempts."""
        self._inner = inner
        self._wait = wait if wait is not None else wait_exponential(multiplier=1, max=8)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the first successful completion or re-raise the last transient error."""
        retrying = Retrying(
            stop=stop_after_attempt(_ATTEMPTS),
            wait=self._wait,
            retry=retry_if_exception_type(TransientLLMError),
            reraise=True,
        )
        return retrying(self._inner.complete, request)


class BudgetedLLMClient:
    """Check the budget before a call and record its cost after."""

    def __init__(self, inner: LLMClient, budget: BudgetGuard) -> None:
        """Wrap inner and charge each completed call to budget."""
        self._inner = inner
        self._budget = budget

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Refuse the call over budget; otherwise complete it and record the cost."""
        self._budget.assert_can_spend()
        response = self._inner.complete(request)
        self._budget.record(response.model, response.usage)
        return response


def guarded_client(
    inner: LLMClient, budget: BudgetGuard, wait: wait_base | None = None
) -> LLMClient:
    """Return budget(retry(inner)): one budget check per logical call, failed attempts uncharged."""
    return BudgetedLLMClient(RetryingLLMClient(inner, wait), budget)
