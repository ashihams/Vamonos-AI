"""Environment-backed process settings."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from costwise.domain.cost import Money


class CrustdataSettings(BaseSettings):
    """The Crustdata key alone, for building fixtures without model or telemetry keys.

    Unrelated keys in a shared .env file are ignored.
    """

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    crustdata_api_key: SecretStr


class NeatlogsSettings(BaseSettings):
    """The neatlogs key alone, for the telemetry smoke check.

    Unrelated keys in a shared .env file are ignored.
    """

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    neatlogs_api_key: SecretStr


DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_LAMBDA_FUNCTION = "costwise-qualify"


class EvalSettings(BaseSettings):
    """Model endpoint, key, budget, paths, and the Lambda target for evaluation runs.

    Unrelated keys in a shared .env file are ignored, and empty values count as unset.
    """

    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", frozen=True, env_ignore_empty=True
    )

    litellm_base_url: str
    litellm_api_key: SecretStr
    model_budget_usd: Money
    neatlogs_api_key: SecretStr | None = None
    otel_collector_endpoint: str = ""
    aws_region: str = DEFAULT_AWS_REGION
    lambda_function_name: str = DEFAULT_LAMBDA_FUNCTION
    config_dir: Path = Path("config")
    runs_dir: Path = Path("runs")
    fixtures_dir: Path = Path("fixtures")


class LambdaSettings(BaseSettings):
    """What the Lambda function needs: the model endpoint and bundled file locations.

    No budget, telemetry, or Crustdata key: the driver accounts for cost and
    the function reads company data from bundled fixtures.
    """

    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", frozen=True, env_ignore_empty=True
    )

    litellm_base_url: str
    litellm_api_key: SecretStr
    config_dir: Path = Path("config")
    fixtures_dir: Path = Path("fixtures")


class AwsSettings(BaseSettings):
    """Region and function name for deploying and tearing down the Lambda function."""

    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", frozen=True, env_ignore_empty=True
    )

    aws_region: str = DEFAULT_AWS_REGION
    lambda_function_name: str = DEFAULT_LAMBDA_FUNCTION
