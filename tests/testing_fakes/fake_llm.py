"""LLM client that replays scripted responses."""

from collections.abc import Callable, Sequence

from costwise.domain.errors import LLMError
from costwise.ports.llm import LLMRequest, LLMResponse


class FakeLLMClient:
    """Replay a list of responses, or call a function, and record requests."""

    def __init__(self, script: Sequence[LLMResponse] | Callable[[LLMRequest], LLMResponse]) -> None:
        """Store the script and start an empty request log."""
        if isinstance(script, Sequence):
            self._respond = _queue(script)
        else:
            self._respond = script
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return the next scripted response."""
        self.requests.append(request)
        return self._respond(request)


def _queue(script: Sequence[LLMResponse]) -> Callable[[LLMRequest], LLMResponse]:
    """Return a function that pops responses in order."""
    pending = list(script)

    def respond(request: LLMRequest) -> LLMResponse:
        """Return the next response, ignoring the request contents."""
        del request
        if not pending:
            raise LLMError("no scripted response")
        return pending.pop(0)

    return respond
