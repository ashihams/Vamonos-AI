"""Run each task as one AWS Lambda invocation and read measured billing from its log."""

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from costwise.adapters.runners.report_line import parse_report_line
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import RunnerError
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest
from costwise.ports.budget import BudgetGuard
from costwise.ports.llm import TokenUsage
from costwise.ports.runner import RunnerCapabilities

UPDATED_WAITER = "function_updated_v2"


class Waiter(Protocol):
    """A boto3 waiter."""

    def wait(self, **kwargs: object) -> None:
        """Block until the resource reaches the waited-for state."""
        ...


class LambdaApi(Protocol):
    """The boto3 Lambda client calls this runner makes."""

    def invoke(self, **kwargs: object) -> Mapping[str, object]:
        """Invoke a function."""
        ...

    def update_function_configuration(self, **kwargs: object) -> Mapping[str, object]:
        """Change a function's configuration."""
        ...

    def get_waiter(self, waiter_name: str) -> Waiter:
        """Return a named waiter."""
        ...


@runtime_checkable
class _Readable(Protocol):
    """A streaming response body."""

    def read(self) -> bytes:
        """Return the whole body."""
        ...


class LambdaRunner:
    """Invoke the deployed function per task; charge the budget from the calls it reports."""

    def __init__(self, client: LambdaApi, function_name: str, budget: BudgetGuard) -> None:
        """Use client to reach function_name and budget to record model spend."""
        self._client = client
        self._function = function_name
        self._budget = budget

    def capabilities(self) -> RunnerCapabilities:
        """Return every lever, with infrastructure cost measured from REPORT lines."""
        return RunnerCapabilities(levers=frozenset(Lever), infra_source=InfraCostSource.MEASURED)

    def apply_infra(self, config: OptimizerConfig) -> None:
        """Set the function's memory and wait until the update finishes."""
        try:
            self._client.update_function_configuration(
                FunctionName=self._function, MemorySize=config.lambda_memory_mb
            )
            self._client.get_waiter(UPDATED_WAITER).wait(FunctionName=self._function)
        except (BotoCoreError, ClientError) as exc:
            raise RunnerError(f"lambda memory update failed: {type(exc).__name__}") from exc

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Invoke once, then merge billed time, memory, and cold start from the log."""
        event = {
            "request": request.model_dump(mode="json"),
            "config": config.model_dump(mode="json"),
        }
        try:
            response = self._client.invoke(
                FunctionName=self._function,
                InvocationType="RequestResponse",
                LogType="Tail",
                Payload=json.dumps(event).encode(),
            )
        except (BotoCoreError, ClientError) as exc:
            raise RunnerError(f"lambda invoke failed: {type(exc).__name__}") from exc
        if response.get("FunctionError"):
            raise RunnerError(f"lambda function error: {response['FunctionError']}")
        invocation = _invocation(response)
        for call in invocation.calls:
            usage = TokenUsage(input_tokens=call.input_tokens, output_tokens=call.output_tokens)
            self._budget.record(call.model, usage)
        report = parse_report_line(_log(response))
        return invocation.model_copy(
            update={
                "billed_ms": report.billed_ms,
                "memory_mb": report.memory_mb,
                "cold_start": report.cold_start,
            }
        )


def _invocation(response: Mapping[str, object]) -> InvocationResult:
    """Parse the function's JSON payload."""
    body = response.get("Payload")
    if not isinstance(body, _Readable):
        raise RunnerError("lambda response has no payload")
    try:
        return InvocationResult.model_validate_json(body.read())
    except ValidationError as exc:
        raise RunnerError("lambda payload is not an invocation result") from exc


def _log(response: Mapping[str, object]) -> str:
    """Decode the base64 log tail."""
    encoded = response.get("LogResult")
    if not isinstance(encoded, str):
        raise RunnerError("lambda response has no log tail")
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8", errors="replace")
    except binascii.Error as exc:
        raise RunnerError("lambda log tail is not base64") from exc
