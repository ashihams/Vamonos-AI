"""Composition root: the only module that chooses concrete adapters."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import httpx

from costwise.adapters.data.crustdata_client import CrustdataClient
from costwise.adapters.data.fixture_source import FixtureCompanySource
from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.adapters.llm.decorators import guarded_client
from costwise.adapters.llm.openai_compatible import OpenAICompatibleClient
from costwise.adapters.runners.local_runner import LocalRunner
from costwise.adapters.storage.file_config_store import FileConfigStore
from costwise.adapters.storage.jsonl_run_store import JsonlRunStore
from costwise.adapters.storage.yaml_loaders import (
    load_guardrail_policy,
    load_icp_rule,
    load_initial_config,
    load_price_book,
    load_workload_policy,
)
from costwise.adapters.system_clock import SystemClock
from costwise.adapters.telemetry.null_sink import NullSink
from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import ConfigError
from costwise.domain.icp import IcpRule
from costwise.domain.labels import WorkloadPolicy
from costwise.domain.task import QualificationRequest
from costwise.ports.data import CompanyDataSource
from costwise.ports.runner import RunnerCapabilities
from costwise.services.baseline import BaselineService
from costwise.services.budget import BudgetService
from costwise.services.evaluation import EvaluationInputs, EvaluationService, EvaluationSinks
from costwise.services.fixtures import FixtureService
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService
from costwise.services.prompt import PromptService
from costwise.services.routing import RoutingService
from costwise.services.task import TaskService, TaskSteps
from costwise.services.workload import WorkloadService
from costwise.settings import CrustdataSettings, EvalSettings

ENV_FILE = Path(".env")


class RunnerKind(StrEnum):
    """Where tasks run."""

    LOCAL = "local"
    LAMBDA = "lambda"


@dataclass(frozen=True, slots=True)
class EvalStack:
    """Everything the eval commands need, already wired."""

    baseline: BaselineService
    config: OptimizerConfig
    requests: tuple[QualificationRequest, ...]
    capabilities: RunnerCapabilities


@dataclass(frozen=True, slots=True)
class FixtureStack:
    """The fixture service and the rule and workload settings used to label."""

    service: FixtureService
    rule: IcpRule
    workload: WorkloadPolicy


@dataclass(frozen=True, slots=True)
class CliDeps:
    """Factories the CLI calls; tests replace them with fakes."""

    eval_stack: Callable[[RunnerKind], AbstractContextManager[EvalStack]]
    fixture_stack: Callable[[Path, Path], FixtureStack]
    crustdata_source: Callable[[], AbstractContextManager[CompanyDataSource]]


def default_cli_deps() -> CliDeps:
    """Return factories that read settings from the environment and the local .env file."""
    return CliDeps(
        eval_stack=open_eval_stack,
        fixture_stack=build_fixture_stack,
        crustdata_source=open_crustdata_source,
    )


def env_file() -> Path | None:
    """Return the local .env file when it exists; process variables still take precedence."""
    return ENV_FILE if ENV_FILE.is_file() else None


@contextmanager
def open_eval_stack(runner_kind: RunnerKind) -> Iterator[EvalStack]:
    """Build the eval stack from settings and close its HTTP client afterwards."""
    settings = EvalSettings(_env_file=env_file())
    with httpx.Client() as http:
        yield build_eval_stack(settings, runner_kind, http)


def build_eval_stack(
    settings: EvalSettings, runner_kind: RunnerKind, http: httpx.Client
) -> EvalStack:
    """Wire the local evaluation stack from config files, fixtures, and the model endpoint."""
    if runner_kind is not RunnerKind.LOCAL:
        raise ConfigError("only the local runner is available until the Lambda stage")
    config_dir = settings.config_dir
    prices = load_price_book(config_dir / "pricing.yaml")
    guardrails = load_guardrail_policy(config_dir / "policy.yaml")
    workload = load_workload_policy(config_dir / "policy.yaml")
    store = JsonFixtureStore(settings.fixtures_dir)
    labels = store.load_labels()
    clock = SystemClock()
    budget = BudgetService(settings.model_budget_usd, guardrails.budget_stop_fraction, prices)
    base_llm = OpenAICompatibleClient(
        http, settings.litellm_base_url, settings.litellm_api_key, clock
    )
    steps = TaskSteps(
        RoutingService(),
        PayloadService(),
        PromptService(),
        ParsingService(),
        load_icp_rule(config_dir / "icp.yaml"),
    )
    task = TaskService(FixtureCompanySource(store), guarded_client(base_llm, budget), steps, clock)
    runner = LocalRunner(task, clock)
    telemetry = NullSink()
    evaluation = EvaluationService(
        runner,
        EvaluationInputs(prices, labels),
        EvaluationSinks(telemetry, JsonlRunStore(settings.runs_dir)),
        budget,
        clock,
    )
    requests = WorkloadService().build(
        labels, workload.n_requests, workload.repeat_ratio, workload.seed
    )
    return EvalStack(
        baseline=BaselineService(evaluation, FileConfigStore(settings.runs_dir), telemetry, budget),
        config=load_initial_config(config_dir / "policy.yaml"),
        requests=requests,
        capabilities=runner.capabilities(),
    )


def build_fixture_stack(fixtures_dir: Path, config_dir: Path) -> FixtureStack:
    """Wire the fixture service over the fixture directory and load labeling settings."""
    return FixtureStack(
        service=FixtureService(JsonFixtureStore(fixtures_dir)),
        rule=load_icp_rule(config_dir / "icp.yaml"),
        workload=load_workload_policy(config_dir / "policy.yaml"),
    )


@contextmanager
def open_crustdata_source() -> Iterator[CompanyDataSource]:
    """Yield a Crustdata client and close its HTTP client afterwards."""
    settings = CrustdataSettings(_env_file=env_file())
    with httpx.Client() as http:
        yield CrustdataClient(http, settings.crustdata_api_key)
