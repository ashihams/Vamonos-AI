"""The Lambda handler and the Lambda composition root, without AWS or the network."""

import shutil
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from costwise.apps.lambda_handler.handler import make_handler
from costwise.bootstrap_lambda import bootstrap_lambda
from costwise.domain.config import OptimizerConfig
from costwise.domain.task import InvocationResult, QualificationRequest
from costwise.services.task import TaskService
from costwise.settings import LambdaSettings
from tests.unit.domain.builders import make_config
from tests.unit.eval_support import make_invocation, make_requests

_REPO_CONFIG = Path(__file__).resolve().parents[3] / "config"
REQUEST = make_requests(0)[0]


class AnsweringTask:
    """Answer fit for every request and record what it was asked."""

    def __init__(self) -> None:
        """Start with no runs."""
        self.runs: list[tuple[QualificationRequest, OptimizerConfig]] = []

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Record the run and return a fit answer."""
        self.runs.append((request, config))
        return make_invocation(request, fit=True)


def _event() -> dict[str, object]:
    """Return the event the Lambda runner sends."""
    return {
        "request": REQUEST.model_dump(mode="json"),
        "config": make_config().model_dump(mode="json"),
    }


def test_handler_runs_the_task_and_returns_json() -> None:
    """The event is parsed, the task runs once, and the invocation comes back as JSON."""
    task = AnsweringTask()
    handler = make_handler(lambda: task)

    body = handler(_event(), None)

    assert InvocationResult.model_validate(body) == make_invocation(REQUEST, fit=True)
    assert task.runs == [(REQUEST, make_config())]


def test_handler_builds_the_task_once_per_container() -> None:
    """Warm invocations reuse the task built on the first one."""
    builds: list[AnsweringTask] = []

    def build() -> AnsweringTask:
        """Build and remember a task."""
        builds.append(AnsweringTask())
        return builds[-1]

    handler = make_handler(build)
    handler(_event(), None)
    handler(_event(), None)

    assert len(builds) == 1
    assert len(builds[0].runs) == 2


def test_handler_rejects_a_malformed_event() -> None:
    """An event without a config fails, which Lambda reports as a function error."""
    with pytest.raises(ValidationError):
        make_handler(AnsweringTask)({"request": REQUEST.model_dump(mode="json")}, None)


def test_bootstrap_lambda_wires_the_task_from_bundled_files(tmp_path: Path) -> None:
    """The task reads the ICP rule from config and companies from bundled fixtures."""
    (tmp_path / "config").mkdir()
    shutil.copy(_REPO_CONFIG / "icp.yaml", tmp_path / "config")
    settings = LambdaSettings(
        litellm_base_url="https://llm.example.test/v1",
        litellm_api_key=SecretStr("sk-test-only"),
        config_dir=tmp_path / "config",
        fixtures_dir=tmp_path / "fixtures",
    )

    assert isinstance(bootstrap_lambda(settings), TaskService)


def test_bootstrap_lambda_reads_settings_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without explicit settings, the environment supplies them."""
    shutil.copy(_REPO_CONFIG / "icp.yaml", tmp_path)
    monkeypatch.setenv("LITELLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-test-only")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FIXTURES_DIR", str(tmp_path))

    assert isinstance(bootstrap_lambda(), TaskService)
