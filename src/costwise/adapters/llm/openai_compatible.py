"""Chat completions against an OpenAI-compatible endpoint such as the LiteLLM proxy."""

import httpx
from pydantic import SecretStr

from costwise.domain.errors import LLMError, TransientLLMError
from costwise.ports.clock import Clock
from costwise.ports.llm import LLMRequest, LLMResponse, TokenUsage

# TODO(VERIFY: LiteLLM proxy accepts max_tokens and returns usage for the chosen models)
TIMEOUT_SECONDS = 60.0
_NS_PER_MS = 1_000_000
_OK = 200
_TOO_MANY_REQUESTS = 429
_SERVER_ERROR = 500


class OpenAICompatibleClient:
    """POST {base_url}/chat/completions with a Bearer key and read text and token usage."""

    def __init__(self, http: httpx.Client, base_url: str, api_key: SecretStr, clock: Clock) -> None:
        """Use the HTTP client, endpoint, key, and clock for latency."""
        self._http = http
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._clock = clock

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the completion; the response model is the requested name so prices match."""
        started = self._clock.now_ns()
        response = self._post(request)
        latency_ms = (self._clock.now_ns() - started) // _NS_PER_MS
        text, usage = _parse(response)
        return LLMResponse(text=text, usage=usage, latency_ms=latency_ms, model=request.model)

    def _post(self, request: LLMRequest) -> httpx.Response:
        """Send the request and classify failures as transient or permanent."""
        try:
            response = self._http.post(
                self._url,
                headers={"authorization": f"Bearer {self._api_key.get_secret_value()}"},
                json={
                    "model": request.model,
                    "messages": [
                        {"role": "system", "content": request.system},
                        {"role": "user", "content": request.user},
                    ],
                    "max_tokens": request.max_output_tokens,
                    "temperature": request.temperature,
                },
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise TransientLLMError("model call timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("model call failed") from exc
        status = response.status_code
        if status == _TOO_MANY_REQUESTS or status >= _SERVER_ERROR:
            raise TransientLLMError(f"model call returned status {status}")
        if status != _OK:
            raise LLMError(f"model call returned status {status}")
        return response


def _parse(response: httpx.Response) -> tuple[str, TokenUsage]:
    """Read choices[0].message.content and usage token counts."""
    try:
        body: object = response.json()
    except ValueError as exc:
        raise LLMError("model response is not JSON") from exc
    if not isinstance(body, dict):
        raise LLMError("model response is malformed")
    text = _first_message_text(body.get("choices"))
    usage = body.get("usage")
    if not isinstance(usage, dict):
        raise LLMError("model response has no usage")
    prompt = _count(usage.get("prompt_tokens"))
    completion = _count(usage.get("completion_tokens"))
    if prompt is None or completion is None:
        raise LLMError("model response has no usage")
    return text, TokenUsage(input_tokens=prompt, output_tokens=completion)


def _first_message_text(choices: object) -> str:
    """Return the first choice's message content."""
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LLMError("model response has no choices")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise LLMError("model response has no text")
    return content


def _count(value: object) -> int | None:
    """Return a non-negative integer token count, or None for anything else."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
