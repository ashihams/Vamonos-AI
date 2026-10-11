"""Run the qualification app in this process and model Lambda billing from wall time."""

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest
from costwise.ports.clock import Clock
from costwise.ports.runner import QualificationTask, RunnerCapabilities

_NS_PER_MS = 1_000_000
_LOCAL_LEVERS = frozenset(
    {Lever.ROUTING, Lever.PAYLOAD_FIELDS, Lever.MAX_OUTPUT_TOKENS, Lever.CACHE}
)


class LocalRunner:
    """In-process runner; memory cannot change wall time here, so that lever is absent."""

    def __init__(self, task: QualificationTask, clock: Clock) -> None:
        """Run task and time it with clock."""
        self._task = task
        self._clock = clock

    def capabilities(self) -> RunnerCapabilities:
        """Return every lever except Lambda memory, with modeled infrastructure cost."""
        return RunnerCapabilities(levers=_LOCAL_LEVERS, infra_source=InfraCostSource.MODELED)

    def apply_infra(self, config: OptimizerConfig) -> None:
        """Do nothing; there is no infrastructure to change locally."""
        del config

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Run the task and bill whole milliseconds of wall time at the configured memory."""
        started = self._clock.now_ns()
        invocation = self._task.run(request, config)
        wall_ns = self._clock.now_ns() - started
        billed_ms = -(-wall_ns // _NS_PER_MS)
        return invocation.model_copy(
            update={"billed_ms": billed_ms, "memory_mb": config.lambda_memory_mb}
        )
