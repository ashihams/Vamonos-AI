"""Retry and budget wrappers and their order."""

import pytest
from tenacity import wait_none

from costwise.adapters.llm.decorators import BudgetedLLMClient, RetryingLLMClient, guarded_client
from costwise.domain.errors import BudgetExceededError, LLMError, TransientLLMError
from costwise.ports.llm import LLMRequest, LLMResponse, TokenUsage
from tests.testing_fakes import FakeLLMClient, RecordingBudget


def _request() -> LLMRequest:
    """Build one request."""
    return LLMRequest(model="cheap-model", system="s", user="u", max_output_tokens=64)


def _response() -> LLMResponse:
    """Build one completion."""
    return LLMResponse(
        text="ok",
        usage=TokenUsage(input_tokens=10, output_tokens=2),
        latency_ms=1,
        model="cheap-model",
    )


def _flaky(failures: list[Exception]) -> FakeLLMClient:
    """Return a fake that raises each failure in turn, then succeeds."""
    pending = list(failures)

    def respond(request: LLMRequest) -> LLMResponse:
        """Raise the next failure or return a completion."""
        del request
        if pending:
            raise pending.pop(0)
        return _response()

    return FakeLLMClient(respond)


def test_retry_only_retries_transient_errors() -> None:
    """Two transient errors are retried; a permanent error is raised at once."""
    transient = _flaky([TransientLLMError("429"), TransientLLMError("503")])
    assert RetryingLLMClient(transient, wait=wait_none()).complete(_request()) == _response()
    assert len(transient.requests) == 3

    permanent = _flaky([LLMError("400")])
    with pytest.raises(LLMError, match="400"):
        RetryingLLMClient(permanent, wait=wait_none()).complete(_request())
    assert len(permanent.requests) == 1


def test_default_wait_is_used_when_none_is_given() -> None:
    """The wrapper builds without an explicit wait and passes successes through."""
    assert RetryingLLMClient(FakeLLMClient([_response()])).complete(_request()) == _response()


def test_budget_checks_before_and_records_after() -> None:
    """A call is charged once; an exhausted budget stops the call before it is made."""
    budget = RecordingBudget()
    inner = FakeLLMClient([_response()])
    BudgetedLLMClient(inner, budget).complete(_request())
    assert budget.checks == 1
    assert budget.charges == [("cheap-model", _response().usage)]

    exhausted = RecordingBudget(exhausted=True)
    untouched = FakeLLMClient([_response()])
    with pytest.raises(BudgetExceededError):
        BudgetedLLMClient(untouched, exhausted).complete(_request())
    assert untouched.requests == []
    assert exhausted.charges == []


def test_guarded_client_checks_budget_once_per_call_and_charges_only_success() -> None:
    """Budget wraps retry: retried attempts share one check and one charge."""
    budget = RecordingBudget()
    inner = _flaky([TransientLLMError("429"), TransientLLMError("500")])
    guarded_client(inner, budget, wait=wait_none()).complete(_request())
    assert len(inner.requests) == 3
    assert budget.checks == 1
    assert len(budget.charges) == 1


def test_guarded_client_charges_nothing_when_retries_are_exhausted() -> None:
    """Three transient failures raise and leave the budget uncharged."""
    budget = RecordingBudget()
    inner = _flaky([TransientLLMError("500")] * 3)
    with pytest.raises(TransientLLMError):
        guarded_client(inner, budget, wait=wait_none()).complete(_request())
    assert budget.charges == []
