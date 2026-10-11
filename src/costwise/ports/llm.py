"""Port for one OpenAI-compatible chat completion."""

from typing import Protocol

from costwise.domain.frozen import FrozenModel


class LLMRequest(FrozenModel):
    """Prompt and limits for one model call."""

    model: str
    system: str
    user: str
    max_output_tokens: int
    temperature: float = 0.0


class TokenUsage(FrozenModel):
    """Token counts reported for one completion."""

    input_tokens: int
    output_tokens: int


class LLMResponse(FrozenModel):
    """Text, token usage, and latency for one completion."""

    text: str
    usage: TokenUsage
    latency_ms: int
    model: str


class LLMClient(Protocol):
    """Completes one prompt."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the completion for the request."""
        ...
