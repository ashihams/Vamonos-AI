"""Composition root inside the Lambda function: bundled fixtures, model endpoint, no telemetry."""

import httpx

from costwise.adapters.data.fixture_source import FixtureCompanySource
from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.adapters.llm.decorators import RetryingLLMClient
from costwise.adapters.llm.openai_compatible import OpenAICompatibleClient
from costwise.adapters.storage.yaml_loaders import load_icp_rule
from costwise.adapters.system_clock import SystemClock
from costwise.ports.runner import QualificationTask
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService
from costwise.services.prompt import PromptService
from costwise.services.routing import RoutingService
from costwise.services.task import TaskService, TaskSteps
from costwise.settings import LambdaSettings


def bootstrap_lambda(settings: LambdaSettings | None = None) -> QualificationTask:
    """Wire the qualification task from environment settings.

    The budget is enforced on the driver, which charges every call this function reports.
    """
    chosen = settings or LambdaSettings()
    clock = SystemClock()
    llm = OpenAICompatibleClient(
        httpx.Client(), chosen.litellm_base_url, chosen.litellm_api_key, clock
    )
    steps = TaskSteps(
        RoutingService(),
        PayloadService(),
        PromptService(),
        ParsingService(),
        load_icp_rule(chosen.config_dir / "icp.yaml"),
    )
    source = FixtureCompanySource(JsonFixtureStore(chosen.fixtures_dir))
    return TaskService(source, RetryingLLMClient(llm), steps, clock)
