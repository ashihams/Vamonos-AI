"""Run a set of requests under one config and turn invocations into scored results."""

import logging
from collections import deque
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from costwise.domain.config import OptimizerConfig
from costwise.domain.cost import PriceBook, breakdown
from costwise.domain.errors import BudgetExceededError, ConfigError
from costwise.domain.labels import CompanyLabel
from costwise.domain.scoring import is_success
from costwise.domain.task import InfraCostSource, QualificationRequest, TaskResult
from costwise.ports.budget import BudgetGuard
from costwise.ports.clock import Clock
from costwise.ports.runner import TaskRunner
from costwise.ports.storage import RunStore
from costwise.ports.telemetry import TelemetrySink

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvaluationInputs:
    """Prices for costing results and ground-truth labels for scoring them."""

    prices: PriceBook
    labels: Mapping[str, CompanyLabel]


@dataclass(frozen=True, slots=True)
class EvaluationSinks:
    """Where finished results go."""

    telemetry: TelemetrySink
    store: RunStore


def with_cache_hits(
    requests: Sequence[QualificationRequest], cache_on: bool
) -> list[QualificationRequest]:
    """Mark repeats of an earlier domain as cache hits when the cache is on."""
    seen: set[str] = set()
    marked: list[QualificationRequest] = []
    for request in requests:
        hit = cache_on and request.domain in seen
        seen.add(request.domain)
        marked.append(request.model_copy(update={"data_cache_hit": hit}))
    return marked


class EvaluationService:
    """Run requests in parallel, score and cost them, and store them in request order."""

    def __init__(
        self,
        runner: TaskRunner,
        inputs: EvaluationInputs,
        sinks: EvaluationSinks,
        budget: BudgetGuard,
        clock: Clock,
    ) -> None:
        """Wire the runner, prices and labels, result sinks, budget guard, and clock."""
        self._runner = runner
        self._inputs = inputs
        self._sinks = sinks
        self._budget = budget
        self._clock = clock

    def evaluate(
        self,
        run_id: str,
        config: OptimizerConfig,
        requests: Sequence[QualificationRequest],
        max_workers: int = 4,
    ) -> list[TaskResult]:
        """Return results in request order; stop submitting once the budget guard trips."""
        if max_workers < 1:
            raise ConfigError("max_workers must be at least 1")
        unlabeled = sorted({r.domain for r in requests} - set(self._inputs.labels))
        if unlabeled:
            raise ConfigError(f"no label for: {', '.join(unlabeled)}")
        prepared = with_cache_hits(requests, config.cache_company_data)
        results = self._run_all(config, prepared, max_workers)
        for result in results:
            self._sinks.telemetry.record_task(run_id, result)
        self._sinks.store.save_results(run_id, config.version, results)
        return results

    def _run_all(
        self, config: OptimizerConfig, requests: list[QualificationRequest], max_workers: int
    ) -> list[TaskResult]:
        """Keep at most max_workers tasks in flight and collect them oldest first."""
        source = self._runner.capabilities().infra_source
        results: list[TaskResult] = []
        inflight: deque[Future[TaskResult]] = deque()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for request in requests:
                if len(inflight) >= max_workers:
                    results.append(inflight.popleft().result())
                try:
                    self._budget.assert_can_spend()
                except BudgetExceededError as exc:
                    _LOG.warning(
                        "budget stop after %d of %d tasks: %s",
                        len(results) + len(inflight),
                        len(requests),
                        exc,
                    )
                    break
                inflight.append(pool.submit(self._run_one, request, config, source))
            results.extend(future.result() for future in inflight)
        return results

    def _run_one(
        self, request: QualificationRequest, config: OptimizerConfig, source: InfraCostSource
    ) -> TaskResult:
        """Run one request and build its scored, costed result."""
        started_at = self._clock.now_ns()
        invocation = self._runner.run(request, config)
        label = self._inputs.labels[request.domain]
        return TaskResult(
            request=request,
            config_version=config.version,
            difficulty=label.difficulty,
            invocation=invocation,
            success=is_success(invocation.answer, label.expected_fit),
            costs=breakdown(invocation, self._inputs.prices),
            infra_source=source,
            started_at_ns=started_at,
        )
