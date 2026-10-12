"""Delete the costwise Lambda function and its execution role.

Usage:
    uv run python infra/aws/teardown.py

Missing resources are skipped, so running it twice is safe.
"""

import logging
import sys

from aws_common import BASIC_EXECUTION_POLICY, NOT_FOUND, ApiCall, error_code, target
from botocore.exceptions import ClientError

from costwise.logging_setup import configure_logging

_LOG = logging.getLogger("costwise.infra.teardown")


def _delete(what: str, call: ApiCall, **kwargs: str) -> None:
    """Make one delete call, treating not-found as already deleted."""
    try:
        call(**kwargs)
    except ClientError as exc:
        if error_code(exc) not in NOT_FOUND:
            raise
        _LOG.info("%s already gone", what)
        return
    _LOG.info("deleted %s", what)


def main() -> int:
    """Delete the function, detach the policy, and delete the role."""
    configure_logging()
    aws = target()
    lam, iam = aws.lambda_client, aws.iam_client
    _delete(f"function {aws.function_name}", lam.delete_function, FunctionName=aws.function_name)
    _delete(
        "basic execution policy attachment",
        iam.detach_role_policy,
        RoleName=aws.role_name,
        PolicyArn=BASIC_EXECUTION_POLICY,
    )
    _delete(f"role {aws.role_name}", iam.delete_role, RoleName=aws.role_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
