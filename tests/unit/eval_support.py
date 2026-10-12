"""Builders for evaluation, baseline, and CLI tests."""

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import (
    CallRecord,
    Difficulty,
    InfraCostSource,
    InvocationResult,
    ModelTier,
    QualificationAnswer,
    QualificationRequest,
    Split,
)
from costwise.services.evaluation import EvaluationInputs, EvaluationService, EvaluationSinks
from tests.testing_fakes import FakeRunner, FixedClock, InMemoryRunStore, RecordingTelemetrySink
from tests.testing_fakes.fake_budget import RecordingBudget
from tests.unit.domain.builders import make_prices

LOCAL_LEVERS = frozenset(
    {Lever.ROUTING, Lever.PAYLOAD_FIELDS, Lever.MAX_OUTPUT_TOKENS, Lever.CACHE}
)


def domain(index: int) -> str:
    """Return the fixture domain for an index."""
    return f"c{index:02d}.example.com"


def make_labels(count: int, heldout: Collection[int] = ()) -> dict[str, CompanyLabel]:
    """Label count companies: even indexes fit and are easy, odd ones do not and are hard."""
    return {
        domain(i): CompanyLabel(
            expected_fit=i % 2 == 0,
            difficulty=Difficulty.EASY if i % 2 == 0 else Difficulty.HARD,
            split=Split.HELDOUT if i in heldout else Split.EVAL,
        )
        for i in range(count)
    }


def split_requests(labels: dict[str, CompanyLabel], *indexes: int) -> list[QualificationRequest]:
    """Return one request per index, with the split its label assigns."""
    return [
        request.model_copy(update={"split": labels[request.domain].split})
        for request in make_requests(*indexes)
    ]


def make_requests(*indexes: int) -> list[QualificationRequest]:
    """Return one request per index, in the given order."""
    return [
        QualificationRequest(
            task_id=f"task-{n:04d}", domain=domain(i), split=Split.EVAL, data_cache_hit=False
        )
        for n, i in enumerate(indexes, start=1)
    ]


def make_invocation(request: QualificationRequest, fit: bool) -> InvocationResult:
    """Return one strong call (1000 in, 100 out) answering fit, with 2 credits unless cached."""
    call = CallRecord(
        model="strong-model",
        tier=ModelTier.STRONG,
        input_tokens=1000,
        output_tokens=100,
        latency_ms=50,
        started_offset_ms=0,
    )
    return InvocationResult(
        task_id=request.task_id,
        answer=QualificationAnswer(icp_fit=fit, reasons=("r",), headcount_band=None, stage=None),
        calls=(call,),
        data_credits=Decimal(0) if request.data_cache_hit else Decimal(2),
        total_latency_ms=60,
        error=None,
        billed_ms=None,
        memory_mb=None,
        cold_start=False,
    )


def answering_runner(labels: dict[str, CompanyLabel], wrong: Collection[str] = ()) -> FakeRunner:
    """Return a runner that answers each label correctly except for the wrong domains."""

    def respond(request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Answer from the label, flipped for wrong domains."""
        del config
        expected = labels[request.domain].expected_fit
        return make_invocation(request, expected != (request.domain in wrong))

    return FakeRunner(LOCAL_LEVERS, InfraCostSource.MODELED, respond)


@dataclass
class EvalHarness:
    """An evaluation service and the fakes behind it."""

    service: EvaluationService
    telemetry: RecordingTelemetrySink
    store: InMemoryRunStore
    budget: RecordingBudget


def make_evaluation(
    runner: FakeRunner, labels: dict[str, CompanyLabel], budget: RecordingBudget | None = None
) -> EvalHarness:
    """Wire an evaluation service over in-memory fakes."""
    telemetry = RecordingTelemetrySink()
    store = InMemoryRunStore()
    guard = budget or RecordingBudget()
    service = EvaluationService(
        runner,
        EvaluationInputs(make_prices(), labels),
        EvaluationSinks(telemetry, store),
        guard,
        FixedClock(1_000),
    )
    return EvalHarness(service, telemetry, store, guard)
