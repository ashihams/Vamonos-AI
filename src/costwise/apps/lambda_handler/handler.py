"""AWS Lambda entry point: parse the event, run one task, return the invocation as JSON."""

from collections.abc import Callable, Mapping
from functools import cache

from costwise.bootstrap_lambda import bootstrap_lambda
from costwise.domain.config import OptimizerConfig
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import QualificationRequest
from costwise.ports.runner import QualificationTask

Handler = Callable[[Mapping[str, object], object], dict[str, object]]


class TaskEvent(FrozenModel):
    """The payload the Lambda runner sends."""

    request: QualificationRequest
    config: OptimizerConfig


def make_handler(build: Callable[[], QualificationTask]) -> Handler:
    """Return a handler that builds the task once per container."""
    task = cache(build)

    def handle(event: Mapping[str, object], context: object) -> dict[str, object]:
        """Run the task in event and return its invocation."""
        del context
        parsed = TaskEvent.model_validate(event)
        return task().run(parsed.request, parsed.config).model_dump(mode="json")

    return handle


handler = make_handler(bootstrap_lambda)
