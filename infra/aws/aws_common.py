"""Names, tags, and typed helpers shared by the deploy and teardown scripts."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import boto3

from costwise.bootstrap import env_file
from costwise.settings import AwsSettings

TAGS = {"project": "costwise"}
BASIC_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
NOT_FOUND = frozenset({"ResourceNotFoundException", "NoSuchEntity"})


class Waiter(Protocol):
    """A boto3 waiter."""

    def wait(self, **kwargs: object) -> None:
        """Block until the resource reaches the waited-for state."""
        ...


class ApiCall(Protocol):
    """One boto3 API operation, called with keyword arguments."""

    def __call__(self, **kwargs: object) -> Mapping[str, object]:
        """Make the call and return the response."""
        ...


class AwsClient(Protocol):
    """A boto3 client: named API calls returning response mappings, plus waiters."""

    def get_waiter(self, waiter_name: str) -> Waiter:
        """Return a named waiter."""
        ...

    def __getattr__(self, name: str) -> ApiCall:
        """Return the API call with this name."""
        ...


@dataclass(frozen=True, slots=True)
class Target:
    """The function and role names, and clients for the configured region."""

    function_name: str
    role_name: str
    lambda_client: AwsClient
    iam_client: AwsClient


def target() -> Target:
    """Read the region and function name from the environment or .env and build clients."""
    settings = AwsSettings(_env_file=env_file())
    session = boto3.session.Session(region_name=settings.aws_region)
    return Target(
        function_name=settings.lambda_function_name,
        role_name=f"{settings.lambda_function_name}-role",
        lambda_client=session.client("lambda"),
        iam_client=session.client("iam"),
    )


def error_code(exc: Exception) -> str:
    """Return the AWS error code of a botocore ClientError, or an empty string."""
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return ""
    error = response.get("Error")
    code = error.get("Code") if isinstance(error, Mapping) else None
    return code if isinstance(code, str) else ""


def text(response: Mapping[str, object], *keys: str) -> str:
    """Return the string at a nested key path, or raise KeyError."""
    current: object = response
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            raise KeyError(".".join(keys))
        current = current[key]
    if not isinstance(current, str):
        raise KeyError(".".join(keys))
    return current
