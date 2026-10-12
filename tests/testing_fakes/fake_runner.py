"""Task runner that replays scripted invocations."""

from collections.abc import Callable, Sequence

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import RunnerError
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest
from costwise.ports.runner import RunnerCapabilities

RunScript = Callable[[QualificationRequest, OptimizerConfig], InvocationResult]


class FakeRunner:
    """Replay invocations, record runs, and record infrastructure updates."""

    def __init__(
        self,
        levers: frozenset[Lever],
        infra_source: InfraCostSource,
        script: Sequence[InvocationResult] | RunScript,
    ) -> None:
        """Store capabilities and the invocation script."""
        self._capabilities = RunnerCapabilities(levers=levers, infra_source=infra_source)
        if isinstance(script, Sequence):
            self._respond = _queue(script)
        else:
            self._respond = script
        self.applied: list[OptimizerConfig] = []
        self.runs: list[tuple[QualificationRequest, OptimizerConfig]] = []

    def capabilities(self) -> RunnerCapabilities:
        """Return the levers and infrastructure source supplied at construction."""
        return self._capabilities

    def apply_infra(self, config: OptimizerConfig) -> None:
        """Record the config whose infrastructure settings were applied."""
        self.applied.append(config)

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Record the run and return the next scripted invocation."""
        self.runs.append((request, config))
        return self._respond(request, config)


def _queue(script: Sequence[InvocationResult]) -> RunScript:
    """Return a function that pops invocations in order."""
    pending = list(script)

    def respond(request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Return the next invocation, ignoring the request and config."""
        del request, config
        if not pending:
            raise RunnerError("no scripted invocation")
        return pending.pop(0)

    return respond
