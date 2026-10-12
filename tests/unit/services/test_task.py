"""TaskService: the qualification pipeline for one request."""

from decimal import Decimal

from costwise.domain.config import OptimizerConfig, RoutingPolicy
from costwise.domain.errors import BudgetExceededError, LLMError
from costwise.domain.task import ModelTier, QualificationRequest, Split
from costwise.ports.data import CompanyFetch
from costwise.ports.llm import LLMRequest, LLMResponse, TokenUsage
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService
from costwise.services.prompt import PromptService
from costwise.services.routing import RoutingService
from costwise.services.task import TaskService, TaskSteps
from tests.testing_fakes import FakeCompanySource, FakeLLMClient, SteppingClock
from tests.unit.domain.builders import make_company, make_config, make_rule

_ANSWER = '{"icp_fit": true, "reasons": ["fits"], "headcount_band": "201-500", "stage": "series_a"}'
_MS = 1_000_000


def _request(domain: str = "example.com", cache_hit: bool = False) -> QualificationRequest:
    """Build one request."""
    return QualificationRequest(
        task_id="task-0001", domain=domain, split=Split.EVAL, data_cache_hit=cache_hit
    )


def _source(missing: bool = False) -> FakeCompanySource:
    """Return a source holding example.com, optionally without open-role data."""
    record = make_company(300, "series_a", None if missing else 20)
    fetch = CompanyFetch(record=record, raw={"headcount": {"total": 300}}, credits_used=Decimal(2))
    return FakeCompanySource({"example.com": fetch})


def _reply(text: str, tokens: int = 100) -> LLMResponse:
    """Build a response; the model field is filled per request by _echo."""
    return LLMResponse(
        text=text, usage=TokenUsage(input_tokens=tokens, output_tokens=10), latency_ms=7, model=""
    )


def _echo(*texts: str) -> FakeLLMClient:
    """Return a fake that replies with texts in order, echoing the requested model."""
    pending = list(texts)

    def respond(request: LLMRequest) -> LLMResponse:
        """Pop the next text, or fail when none are left."""
        if not pending:
            raise LLMError("model call returned status 400")
        return _reply(pending.pop(0)).model_copy(update={"model": request.model})

    return FakeLLMClient(respond)


def _service(llm: FakeLLMClient, source: FakeCompanySource | None = None) -> TaskService:
    """Wire a TaskService with real steps and a clock that advances 1 ms per read."""
    steps = TaskSteps(
        RoutingService(), PayloadService(), PromptService(), ParsingService(), make_rule()
    )
    return TaskService(source or _source(), llm, steps, SteppingClock(0, _MS))


def _cheap_config(missing: int = 0, fields: tuple[str, ...] | None = None) -> OptimizerConfig:
    """Return the starting config switched to cheap-by-default routing."""
    policy = RoutingPolicy(
        default_tier=ModelTier.CHEAP,
        strong_if_missing_fields_gte=missing,
        strong_if_near_threshold=False,
    )
    return make_config().model_copy(update={"routing": policy, "payload_fields": fields})


def test_normal_path_returns_answer_one_call_and_credits() -> None:
    """One strong call parses; credits, latency, and runner-owned fields are set."""
    llm = _echo(_ANSWER)
    result = _service(llm).run(_request(), make_config())
    assert result.error is None
    assert result.answer is not None
    assert result.answer.icp_fit is True
    assert [(c.model, c.tier) for c in result.calls] == [("strong-model", ModelTier.STRONG)]
    assert result.calls[0].input_tokens == 100
    assert result.calls[0].latency_ms == 7
    assert result.calls[0].started_offset_ms == 1
    assert result.total_latency_ms == 2
    assert result.data_credits == Decimal(2)
    assert (result.billed_ms, result.memory_mb, result.cold_start) == (None, None, False)
    assert llm.requests[0].max_output_tokens == 512
    assert '"headcount"' in llm.requests[0].user


def test_cache_hit_zeroes_credits_and_trimmed_payload_is_sent() -> None:
    """A cached company costs no credits; listed fields replace the raw payload."""
    llm = _echo(_ANSWER)
    config = _cheap_config(fields=("employee_count",))
    result = _service(llm).run(_request(cache_hit=True), config)
    assert result.data_credits == Decimal(0)
    assert llm.requests[0].model == "cheap-model"
    assert '{"employee_count":300}' in llm.requests[0].user
    assert '"headcount"' not in llm.requests[0].user


def test_parse_failure_retries_once_on_strong_and_records_both_calls() -> None:
    """A bad cheap answer is retried on the strong tier; both calls are in the result."""
    llm = _echo("not json", _ANSWER)
    result = _service(llm).run(_request(), _cheap_config())
    assert result.error is None
    assert result.answer is not None
    assert [(c.model, c.tier) for c in result.calls] == [
        ("cheap-model", ModelTier.CHEAP),
        ("strong-model", ModelTier.STRONG),
    ]
    assert result.calls[1].started_offset_ms > result.calls[0].started_offset_ms


def test_second_parse_failure_becomes_error_with_both_calls() -> None:
    """Only one fallback is made; a second bad answer is reported, not raised."""
    result = _service(_echo("nope", "still nope")).run(_request(), _cheap_config())
    assert result.answer is None
    assert result.error is not None
    assert result.error.startswith("ParseError")
    assert len(result.calls) == 2


def test_llm_budget_and_data_failures_become_errors() -> None:
    """Model errors, a tripped budget, and unknown domains return results with error set."""
    llm_failed = _service(_echo()).run(_request(), make_config())
    assert llm_failed.error == "LLMError: model call returned status 400"
    assert llm_failed.calls == ()
    assert llm_failed.data_credits == Decimal(2)

    def over_budget(request: LLMRequest) -> LLMResponse:
        """Refuse every call."""
        del request
        raise BudgetExceededError("stop line reached")

    tripped = _service(FakeLLMClient(over_budget)).run(_request(), make_config())
    assert tripped.error == "BudgetExceededError: stop line reached"

    missing = _service(_echo(_ANSWER)).run(_request(domain="unknown.com"), make_config())
    assert missing.error is not None
    assert missing.error.startswith("DataSourceError")
    assert missing.data_credits == Decimal(0)


def test_routing_thresholds_choose_the_tier() -> None:
    """A company missing open-role data goes strong when the threshold is 1, cheap when 2."""
    escalated = _echo(_ANSWER)
    _service(escalated, _source(missing=True)).run(_request(), _cheap_config(missing=1))
    assert escalated.requests[0].model == "strong-model"

    kept_cheap = _echo(_ANSWER)
    _service(kept_cheap, _source(missing=True)).run(_request(), _cheap_config(missing=2))
    assert kept_cheap.requests[0].model == "cheap-model"
