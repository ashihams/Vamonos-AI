"""Qualify one company: fetch, route, prompt, call, parse, with one strong fallback."""

from dataclasses import dataclass
from decimal import Decimal

from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import BudgetExceededError, DataSourceError, LLMError, ParseError
from costwise.domain.icp import IcpRule
from costwise.domain.task import (
    CallRecord,
    InvocationResult,
    ModelTier,
    QualificationAnswer,
    QualificationRequest,
)
from costwise.ports.clock import Clock
from costwise.ports.data import CompanyDataSource
from costwise.ports.llm import LLMClient, LLMRequest
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService
from costwise.services.prompt import PromptService
from costwise.services.routing import RoutingService

_NS_PER_MS = 1_000_000
_FAILURES = (DataSourceError, LLMError, BudgetExceededError, ParseError)


@dataclass(frozen=True, slots=True)
class TaskSteps:
    """The pure pipeline steps and the ICP rule they share."""

    router: RoutingService
    payloads: PayloadService
    prompts: PromptService
    parser: ParsingService
    rule: IcpRule


@dataclass(frozen=True, slots=True)
class _Prompt:
    """Rendered prompts for one company."""

    system: str
    user: str


class TaskService:
    """Run the qualification app for one request; failures become result errors."""

    def __init__(
        self, data_source: CompanyDataSource, llm: LLMClient, steps: TaskSteps, clock: Clock
    ) -> None:
        """Wire the data source, model client, pipeline steps, and clock."""
        self._data = data_source
        self._llm = llm
        self._steps = steps
        self._clock = clock

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Qualify the request's company under config and return the invocation result."""
        started = self._clock.now_ns()
        calls: list[CallRecord] = []
        credits = Decimal(0)
        answer: QualificationAnswer | None = None
        error: str | None = None
        try:
            fetch = self._data.fetch(request.domain)
            credits = Decimal(0) if request.data_cache_hit else fetch.credits_used
            steps = self._steps
            tier = steps.router.choose(fetch.record, config.routing, steps.rule)
            payload = steps.payloads.trim(fetch.record, fetch.raw, config.payload_fields)
            system, user = steps.prompts.build(payload, steps.rule)
            answer = self._answer(_Prompt(system, user), tier, config, (started, calls))
        except _FAILURES as exc:
            error = f"{type(exc).__name__}: {exc}"
        return InvocationResult(
            task_id=request.task_id,
            answer=answer,
            calls=tuple(calls),
            data_credits=credits,
            total_latency_ms=(self._clock.now_ns() - started) // _NS_PER_MS,
            error=error,
            billed_ms=None,
            memory_mb=None,
            cold_start=False,
        )

    def _answer(
        self,
        prompt: _Prompt,
        tier: ModelTier,
        config: OptimizerConfig,
        trace: tuple[int, list[CallRecord]],
    ) -> QualificationAnswer:
        """Call the routed tier; on a parse failure call the strong tier once more."""
        text = self._call(prompt, tier, config, trace)
        try:
            return self._steps.parser.parse(text)
        except ParseError:
            retry_text = self._call(prompt, ModelTier.STRONG, config, trace)
            return self._steps.parser.parse(retry_text)

    def _call(
        self,
        prompt: _Prompt,
        tier: ModelTier,
        config: OptimizerConfig,
        trace: tuple[int, list[CallRecord]],
    ) -> str:
        """Make one model call, append its CallRecord, and return the text."""
        started, calls = trace
        model = config.cheap_model if tier is ModelTier.CHEAP else config.strong_model
        offset_ms = (self._clock.now_ns() - started) // _NS_PER_MS
        response = self._llm.complete(
            LLMRequest(
                model=model,
                system=prompt.system,
                user=prompt.user,
                max_output_tokens=config.max_output_tokens,
            )
        )
        calls.append(
            CallRecord(
                model=response.model,
                tier=tier,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=response.latency_ms,
                started_offset_ms=offset_ms,
            )
        )
        return response.text
