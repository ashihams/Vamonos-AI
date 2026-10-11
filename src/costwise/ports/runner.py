"""Port for running one qualification task."""

from typing import Protocol

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest


class RunnerCapabilities(FrozenModel):
    """Levers a runner can apply and how it prices infrastructure."""

    levers: frozenset[Lever]
    infra_source: InfraCostSource


class QualificationTask(Protocol):
    """The qualification app a runner executes."""

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Qualify one company and return the invocation without runner fields."""
        ...


class TaskRunner(Protocol):
    """Runs one qualification and can apply infrastructure settings."""

    def capabilities(self) -> RunnerCapabilities:
        """Return the levers and infrastructure source this runner supports."""
        ...

    def apply_infra(self, config: OptimizerConfig) -> None:
        """Apply infrastructure settings from the config."""
        ...

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Run one task and return its invocation."""
        ...
