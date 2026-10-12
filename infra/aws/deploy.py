"""Build the Lambda zip, then create or update the function and its execution role.

Usage:
    uv run python infra/aws/deploy.py build    # build the zip only; no AWS calls
    uv run python infra/aws/deploy.py deploy   # build, then create or update in AWS

Creates only an IAM role (basic execution policy) and one Lambda function, both
tagged project=costwise. Run `make lambda-teardown` after recording the demo.
"""

import json
import logging
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from aws_common import BASIC_EXECUTION_POLICY, TAGS, AwsClient, Target, error_code, target, text
from botocore.exceptions import ClientError

from costwise.adapters.storage.yaml_loaders import load_initial_config
from costwise.bootstrap import env_file
from costwise.logging_setup import configure_logging
from costwise.settings import LambdaSettings

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
PACKAGE = BUILD / "lambda"
ZIP_PATH = BUILD / "costwise-lambda.zip"
HANDLER = "costwise.apps.lambda_handler.handler.handler"
RUNTIME = "python3.12"
TIMEOUT_S = 60
TASK_ROOT = "/var/task"
ROLE_RETRIES = 10
ROLE_RETRY_S = 6
TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

_LOG = logging.getLogger("costwise.infra.deploy")


def _uv(*args: str) -> None:
    """Run one uv command from the repository root, failing loudly."""
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is not on PATH")
    subprocess.run([uv, *args], cwd=ROOT, check=True)  # noqa: S603 - fixed arguments


def build() -> Path:
    """Install Linux wheels for the runtime dependencies and zip them with the code."""
    shutil.rmtree(BUILD, ignore_errors=True)
    PACKAGE.mkdir(parents=True)
    requirements = BUILD / "requirements.txt"
    _uv(
        "export", "--no-dev", "--no-hashes", "--no-emit-project", "--output-file", str(requirements)
    )
    _uv(
        "pip", "install", "--target", str(PACKAGE), "--python-platform", "x86_64-manylinux2014",
        "--python-version", "3.12", "--only-binary", ":all:", "-r", str(requirements),
    )  # fmt: skip
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "src" / "costwise", PACKAGE / "costwise", ignore=ignore)
    shutil.copytree(ROOT / "fixtures" / "raw", PACKAGE / "fixtures" / "raw")
    (PACKAGE / "config").mkdir()
    shutil.copy2(ROOT / "config" / "icp.yaml", PACKAGE / "config" / "icp.yaml")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE).as_posix())
    _LOG.info("built %s (%.1f MB)", ZIP_PATH, ZIP_PATH.stat().st_size / 1_000_000)
    return ZIP_PATH


def _ensure_role(iam: AwsClient, role_name: str) -> str:
    """Create the execution role with the basic policy, or reuse it; return its ARN."""
    try:
        created = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Tags=[{"Key": key, "Value": value} for key, value in TAGS.items()],
        )
        arn = text(created, "Role", "Arn")
    except ClientError as exc:
        if error_code(exc) != "EntityAlreadyExists":
            raise
        arn = text(iam.get_role(RoleName=role_name), "Role", "Arn")
    iam.attach_role_policy(RoleName=role_name, PolicyArn=BASIC_EXECUTION_POLICY)
    return arn


def _function_exists(lam: AwsClient, name: str) -> bool:
    """Return whether the function already exists."""
    try:
        lam.get_function(FunctionName=name)
    except ClientError as exc:
        if error_code(exc) == "ResourceNotFoundException":
            return False
        raise
    return True


def _create(lam: AwsClient, name: str, role_arn: str, settings: dict[str, object]) -> None:
    """Create the function, retrying while a new role is still propagating."""
    for attempt in range(1, ROLE_RETRIES + 1):
        try:
            lam.create_function(FunctionName=name, Role=role_arn, **settings)
            return
        except ClientError as exc:
            if error_code(exc) != "InvalidParameterValueException" or attempt == ROLE_RETRIES:
                raise
            _LOG.info("role not assumable yet; retry %d of %d", attempt, ROLE_RETRIES)
            time.sleep(ROLE_RETRY_S)


def deploy() -> None:
    """Build, then create or update the role and function."""
    zip_bytes = build().read_bytes()
    model = LambdaSettings(_env_file=env_file())
    aws: Target = target()
    memory = load_initial_config(ROOT / "config" / "policy.yaml").lambda_memory_mb
    environment = {
        "Variables": {
            "LITELLM_BASE_URL": model.litellm_base_url,
            "LITELLM_API_KEY": model.litellm_api_key.get_secret_value(),
            "FIXTURES_DIR": f"{TASK_ROOT}/fixtures",
            "CONFIG_DIR": f"{TASK_ROOT}/config",
        }
    }
    role_arn = _ensure_role(aws.iam_client, aws.role_name)
    lam, name = aws.lambda_client, aws.function_name
    shared: dict[str, object] = {
        "Timeout": TIMEOUT_S,
        "MemorySize": memory,
        "Environment": environment,
    }
    if _function_exists(lam, name):
        lam.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        lam.get_waiter("function_updated_v2").wait(FunctionName=name)
        lam.update_function_configuration(FunctionName=name, Role=role_arn, **shared)
        lam.get_waiter("function_updated_v2").wait(FunctionName=name)
    else:
        create = {"Runtime": RUNTIME, "Handler": HANDLER, "Code": {"ZipFile": zip_bytes}}
        _create(lam, name, role_arn, {**shared, **create, "Tags": TAGS})
        lam.get_waiter("function_active_v2").wait(FunctionName=name)
    _LOG.info("deployed %s with %d MB; run `make lambda-teardown` after the demo", name, memory)


def main() -> int:
    """Dispatch build or deploy."""
    configure_logging()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        build()
    elif command == "deploy":
        deploy()
    else:
        _LOG.error("usage: deploy.py build|deploy")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
