"""Environment-backed process settings."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from costwise.domain.cost import Money


class Settings(BaseSettings):
    """Keys, endpoints, budget, and paths read from the process environment."""

    model_config = SettingsConfigDict(env_file=None, extra="forbid", frozen=True)

    litellm_base_url: str
    litellm_api_key: SecretStr
    crustdata_api_key: SecretStr
    neatlogs_api_key: SecretStr
    model_budget_usd: Money
    aws_region: str = ""
    lambda_function_name: str = ""
    grpc_dns_resolver: str = ""
    config_dir: Path = Path("config")
    runs_dir: Path = Path("runs")


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


class EvalSettings(BaseSettings):
    """Model endpoint, key, budget, and paths for local evaluation runs.

    Unrelated keys in a shared .env file are ignored.
    """

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    litellm_base_url: str
    litellm_api_key: SecretStr
    model_budget_usd: Money
    neatlogs_api_key: SecretStr | None = None
    otel_collector_endpoint: str = ""
    config_dir: Path = Path("config")
    runs_dir: Path = Path("runs")
    fixtures_dir: Path = Path("fixtures")
