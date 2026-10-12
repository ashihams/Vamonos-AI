"""OpenAICompatibleClient against mocked chat completion responses."""

import json

import httpx
import pytest
import respx
from pydantic import SecretStr
from tenacity import wait_none

from costwise.adapters.llm.decorators import RetryingLLMClient
from costwise.adapters.llm.openai_compatible import OpenAICompatibleClient
from costwise.domain.errors import LLMError, TransientLLMError
from costwise.ports.llm import LLMRequest
from tests.testing_fakes import TickingClock

_BASE = "https://llm.example.test/v1/"
_URL = "https://llm.example.test/v1/chat/completions"


def _completion(text: str = '{"icp_fit": true}') -> dict[str, object]:
    """Return an OpenAI-style chat completion body."""
    return {
        "id": "chatcmpl-1",
        "model": "provider-model-id",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    }


def _request() -> LLMRequest:
    """Build one request."""
    return LLMRequest(
        model="cheap-model", system="system text", user="user text", max_output_tokens=256
    )


def _client(http: httpx.Client, ticks: list[int]) -> OpenAICompatibleClient:
    """Build a client whose clock returns the given ticks."""
    return OpenAICompatibleClient(http, _BASE, SecretStr("test-key"), TickingClock(ticks))


@respx.mock
def test_success_reads_text_usage_latency_and_sends_the_request() -> None:
    """Text, token usage, and clock latency are returned; the body follows the chat schema."""
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_completion()))
    with httpx.Client() as http:
        response = _client(http, [1_000_000_000, 1_250_000_000]).complete(_request())
    assert response.text == '{"icp_fit": true}'
    assert response.usage.input_tokens == 120
    assert response.usage.output_tokens == 30
    assert response.latency_ms == 250
    assert response.model == "cheap-model"
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer test-key"
    body = json.loads(sent.content)
    assert body["model"] == "cheap-model"
    assert body["max_tokens"] == 256
    assert body["temperature"] == 0.0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


@respx.mock
def test_429_then_success_is_retried_by_the_retrying_wrapper() -> None:
    """A rate limit is transient; the retry wrapper makes a second attempt that succeeds."""
    route = respx.post(_URL)
    route.side_effect = [httpx.Response(429), httpx.Response(200, json=_completion())]
    with httpx.Client() as http:
        client = RetryingLLMClient(_client(http, [0, 1, 2, 3]), wait=wait_none())
        assert client.complete(_request()).usage.output_tokens == 30
    assert route.call_count == 2


@respx.mock
def test_500_exhaustion_raises_after_three_attempts() -> None:
    """Three server errors exhaust the retries and surface a transient LLMError."""
    route = respx.post(_URL).mock(return_value=httpx.Response(500))
    with httpx.Client() as http:
        client = RetryingLLMClient(_client(http, [0] * 6), wait=wait_none())
        with pytest.raises(TransientLLMError, match="status 500"):
            client.complete(_request())
    assert route.call_count == 3


@respx.mock
def test_timeouts_are_transient_and_other_failures_are_not() -> None:
    """Timeouts are transient; 400, transport errors, and malformed bodies are permanent."""
    route = respx.post(_URL)
    route.side_effect = [httpx.ReadTimeout("slow")]
    with httpx.Client() as http:
        with pytest.raises(TransientLLMError, match="timed out"):
            _client(http, [0, 1]).complete(_request())
        no_usage = {"choices": [{"message": {"content": "x"}}]}
        bad_usage = {**no_usage, "usage": {"prompt_tokens": True, "completion_tokens": 1}}
        cases = [
            (httpx.Response(400), "status 400"),
            (httpx.ConnectError("down"), "call failed"),
            (httpx.Response(200, content=b"not json"), "not JSON"),
            (httpx.Response(200, json=["list"]), "malformed"),
            (httpx.Response(200, json={"choices": []}), "no choices"),
            (httpx.Response(200, json={"choices": [{"message": {"content": None}}]}), "no text"),
            (httpx.Response(200, json=no_usage), "no usage"),
            (httpx.Response(200, json=bad_usage), "no usage"),
        ]
        for outcome, message in cases:
            route.side_effect = [outcome]
            with pytest.raises(LLMError, match=message) as caught:
                _client(http, [0, 1]).complete(_request())
            assert not isinstance(caught.value, TransientLLMError)
