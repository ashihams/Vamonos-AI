"""LambdaRunner against a stubbed boto3 Lambda client; nothing reaches AWS."""

import base64
import io
import json
from collections.abc import Iterator
from decimal import Decimal

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from costwise.adapters.runners.lambda_runner import LambdaApi, LambdaRunner
from costwise.domain.config import Lever
from costwise.domain.errors import RunnerError
from costwise.domain.task import InfraCostSource
from costwise.ports.llm import TokenUsage
from tests.testing_fakes import RecordingBudget
from tests.unit.domain.builders import make_config
from tests.unit.eval_support import make_invocation, make_requests

FUNCTION = "costwise-qualify"
REQUEST = make_requests(0)[0]
COLD_LOG = (
    "START RequestId: r1 Version: $LATEST\n"
    "REPORT RequestId: r1\tDuration: 812.40 ms\tBilled Duration: 813 ms\t"
    "Memory Size: 512 MB\tMax Memory Used: 140 MB\tInit Duration: 640.12 ms\t\n"
)


def _body(data: bytes) -> StreamingBody:
    """Wrap bytes as a botocore streaming body."""
    return StreamingBody(io.BytesIO(data), len(data))


def _response(payload: bytes, log: str | None = COLD_LOG) -> dict[str, object]:
    """Return an invoke response with a payload and, unless log is None, a base64 log tail."""
    response: dict[str, object] = {"StatusCode": 200, "Payload": _body(payload)}
    if log is not None:
        response["LogResult"] = base64.b64encode(log.encode()).decode()
    return response


@pytest.fixture
def stubbed() -> Iterator[tuple[LambdaApi, Stubber]]:
    """Yield a Lambda client whose calls are answered by a Stubber."""
    client = boto3.client(
        "lambda",
        region_name="us-east-1",
        aws_access_key_id="test-only",
        aws_secret_access_key="test-only",  # noqa: S106 - fake credentials
    )
    with Stubber(client) as stubber:
        yield client, stubber
        stubber.assert_no_pending_responses()


def _expected_invoke() -> dict[str, object]:
    """Return the invoke parameters the runner must send."""
    event = {
        "request": REQUEST.model_dump(mode="json"),
        "config": make_config().model_dump(mode="json"),
    }
    return {
        "FunctionName": FUNCTION,
        "InvocationType": "RequestResponse",
        "LogType": "Tail",
        "Payload": json.dumps(event).encode(),
    }


def test_run_merges_measured_billing_and_charges_the_budget(
    stubbed: tuple[LambdaApi, Stubber],
) -> None:
    """Billed time, memory, and cold start come from the REPORT line; calls are charged."""
    client, stubber = stubbed
    invocation = make_invocation(REQUEST, fit=True)
    stubber.add_response(
        "invoke", _response(invocation.model_dump_json().encode()), _expected_invoke()
    )
    budget = RecordingBudget()

    result = LambdaRunner(client, FUNCTION, budget).run(REQUEST, make_config())

    assert (result.billed_ms, result.memory_mb, result.cold_start) == (813, 512, True)
    assert result.answer == invocation.answer
    assert result.data_credits == Decimal(2)
    assert budget.charges == [("strong-model", TokenUsage(input_tokens=1000, output_tokens=100))]


def test_function_error_is_a_runner_error(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """An unhandled exception inside the function surfaces as RunnerError."""
    client, stubber = stubbed
    response = _response(b'{"errorMessage": "boom"}') | {"FunctionError": "Unhandled"}
    stubber.add_response("invoke", response)

    with pytest.raises(RunnerError, match="function error: Unhandled"):
        LambdaRunner(client, FUNCTION, RecordingBudget()).run(REQUEST, make_config())


def test_invoke_failure_is_a_runner_error(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """A throttled invoke surfaces as RunnerError naming the exception type only."""
    client, stubber = stubbed
    stubber.add_client_error("invoke", "TooManyRequestsException", http_status_code=429)

    with pytest.raises(RunnerError, match="invoke failed: TooManyRequestsException"):
        LambdaRunner(client, FUNCTION, RecordingBudget()).run(REQUEST, make_config())


VALID_PAYLOAD = make_invocation(REQUEST, fit=True).model_dump_json().encode()


@pytest.mark.parametrize(
    ("payload", "log", "message"),
    [
        (b"not json", COLD_LOG, "not an invocation result"),
        (VALID_PAYLOAD, None, "no log tail"),
        (VALID_PAYLOAD, "no report here", "no REPORT line"),
    ],
)
def test_bad_responses_are_runner_errors(
    stubbed: tuple[LambdaApi, Stubber], payload: bytes, log: str | None, message: str
) -> None:
    """A bad payload, a missing log tail, or a log without REPORT is refused."""
    client, stubber = stubbed
    stubber.add_response("invoke", _response(payload, log))

    with pytest.raises(RunnerError, match=message):
        LambdaRunner(client, FUNCTION, RecordingBudget()).run(REQUEST, make_config())


def test_missing_payload_is_a_runner_error(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """A response without a payload body is refused."""
    client, stubber = stubbed
    stubber.add_response("invoke", {"StatusCode": 200})

    with pytest.raises(RunnerError, match="no payload"):
        LambdaRunner(client, FUNCTION, RecordingBudget()).run(REQUEST, make_config())


def test_undecodable_log_tail_is_a_runner_error(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """A log tail that is not base64 is refused."""
    client, stubber = stubbed
    stubber.add_response("invoke", _response(VALID_PAYLOAD) | {"LogResult": "not base64!"})

    with pytest.raises(RunnerError, match="not base64"):
        LambdaRunner(client, FUNCTION, RecordingBudget()).run(REQUEST, make_config())


def test_apply_infra_sets_memory_and_waits(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """The memory update is followed by the function-updated waiter."""
    client, stubber = stubbed
    config = make_config().model_copy(update={"lambda_memory_mb": 512})
    stubber.add_response(
        "update_function_configuration", {}, {"FunctionName": FUNCTION, "MemorySize": 512}
    )
    stubber.add_response(
        "get_function",
        {"Configuration": {"LastUpdateStatus": "Successful"}},
        {"FunctionName": FUNCTION},
    )

    LambdaRunner(client, FUNCTION, RecordingBudget()).apply_infra(config)


def test_apply_infra_failure_is_a_runner_error(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """A refused memory update surfaces as RunnerError."""
    client, stubber = stubbed
    stubber.add_client_error("update_function_configuration", "ResourceConflictException")

    with pytest.raises(RunnerError, match="memory update failed"):
        LambdaRunner(client, FUNCTION, RecordingBudget()).apply_infra(make_config())


def test_capabilities_are_every_lever_measured(stubbed: tuple[LambdaApi, Stubber]) -> None:
    """Lambda can change memory and measures infrastructure cost."""
    client, _ = stubbed
    capabilities = LambdaRunner(client, FUNCTION, RecordingBudget()).capabilities()

    assert capabilities.levers == frozenset(Lever)
    assert capabilities.infra_source is InfraCostSource.MEASURED
