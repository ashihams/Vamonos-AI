"""Composition root: the only module that chooses concrete adapters."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import boto3
import httpx

from costwise.adapters.approval.auto_approver import AutoApprover
from costwise.adapters.approval.cli_approver import CliApprover
from costwise.adapters.data.crustdata_client import CrustdataClient
from costwise.adapters.data.fixture_source import FixtureCompanySource
from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.adapters.llm.decorators import guarded_client
from costwise.adapters.llm.openai_compatible import OpenAICompatibleClient
from costwise.adapters.runners.lambda_runner import LambdaRunner
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
from costwise.adapters.telemetry.exporters import (
    collector_meter_provider,
    neatlogs_tracer_provider,
)
from costwise.adapters.telemetry.null_sink import NullSink
from costwise.adapters.telemetry.otel_sink import OtelSink
from costwise.domain.config import OptimizerConfig
from costwise.domain.icp import IcpRule
from costwise.domain.labels import WorkloadPolicy
from costwise.domain.task import QualificationRequest
from costwise.ports.approval import Approver
from costwise.ports.clock import Clock
from costwise.ports.data import CompanyDataSource
from costwise.ports.llm import LLMClient
from costwise.ports.runner import RunnerCapabilities, TaskRunner
from costwise.ports.telemetry import TelemetrySink
from costwise.services.baseline import BaselineService
from costwise.services.budget import BudgetService
from costwise.services.evaluation import EvaluationInputs, EvaluationService, EvaluationSinks
from costwise.services.fixtures import FixtureService
from costwise.services.iteration import IterationDeciders, IterationService, IterationStores
from costwise.services.llm_proposer import LLMProposer
from costwise.services.optimizer import OptimizerService
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService
from costwise.services.prompt import PromptService
from costwise.services.proposers import HeuristicProposer
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
    iteration_with: Callable[[Approver], IterationService]


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
    approver: Callable[[bool], Approver]


def default_cli_deps() -> CliDeps:
    """Return factories that read settings from the environment and the local .env file."""
    return CliDeps(
        eval_stack=open_eval_stack,
        fixture_stack=build_fixture_stack,
        crustdata_source=open_crustdata_source,
        approver=build_approver,
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
    """Wire evaluation from config files, fixtures, the model endpoint, and the chosen runner.

    The driver's model client still serves the optimizer when tasks run on Lambda.
    """
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
    llm = guarded_client(base_llm, budget)
    runner: TaskRunner
    if runner_kind is RunnerKind.LAMBDA:
        runner = build_lambda_runner(settings, budget)
    else:
        runner = _local_runner(store, llm, config_dir, clock)
    telemetry = build_telemetry(settings, clock)
    runs = JsonlRunStore(settings.runs_dir)
    configs = FileConfigStore(settings.runs_dir)
    evaluation = EvaluationService(
        runner, EvaluationInputs(prices, labels), EvaluationSinks(telemetry, runs), budget, clock
    )
    requests = WorkloadService().build(
        labels, workload.n_requests, workload.repeat_ratio, workload.seed
    )
    config = load_initial_config(config_dir / "policy.yaml")
    optimizer = OptimizerService(LLMProposer(llm, config.strong_model), HeuristicProposer())
    stores = IterationStores(runs, configs, telemetry)

    def iteration_with(approver: Approver) -> IterationService:
        """Wire the iteration loop around the chosen approver."""
        deciders = IterationDeciders(optimizer, approver, guardrails)
        return IterationService(evaluation, runner, deciders, stores, budget)

    return EvalStack(
        baseline=BaselineService(evaluation, configs, telemetry, budget),
        config=config,
        requests=requests,
        capabilities=runner.capabilities(),
        iteration_with=iteration_with,
    )


def _local_runner(
    store: JsonFixtureStore, llm: LLMClient, config_dir: Path, clock: Clock
) -> LocalRunner:
    """Run the qualification task in this process over local fixtures."""
    steps = TaskSteps(
        RoutingService(),
        PayloadService(),
        PromptService(),
        ParsingService(),
        load_icp_rule(config_dir / "icp.yaml"),
    )
    return LocalRunner(TaskService(FixtureCompanySource(store), llm, steps, clock), clock)


def build_lambda_runner(settings: EvalSettings, budget: BudgetService) -> LambdaRunner:
    """Invoke the deployed function with the default AWS credential chain."""
    client = boto3.client("lambda", region_name=settings.aws_region)
    return LambdaRunner(client, settings.lambda_function_name, budget)


def build_approver(auto_approve: bool) -> Approver:
    """Approve everything when asked to, otherwise ask a human in the terminal."""
    return AutoApprover() if auto_approve else CliApprover()


def build_telemetry(settings: EvalSettings, clock: Clock) -> TelemetrySink:
    """Export to neatlogs when its key is set, metrics to a Collector when one is configured."""
    if settings.neatlogs_api_key is None:
        return NullSink()
    endpoint = settings.otel_collector_endpoint
    meters = collector_meter_provider(endpoint) if endpoint else None
    return OtelSink(neatlogs_tracer_provider(settings.neatlogs_api_key), meters, clock)


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
