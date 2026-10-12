"""End to end: the real bootstrap, fixtures on disk, .env settings, and a mocked model endpoint."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import SecretStr
from typer.testing import CliRunner

from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.apps.cli.main import app
from costwise.bootstrap import RunnerKind, build_eval_stack
from costwise.domain.company import CompanyRecord
from costwise.domain.config import Lever
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import Difficulty, InfraCostSource, Split
from costwise.ports.data import CompanyFetch
from costwise.settings import EvalSettings

_REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"
_URL = "https://llm.example.test/v1/chat/completions"
_ENV_NAMES = (
    "NEATLOGS_API_KEY",
    "OTEL_COLLECTOR_ENDPOINT",
    "LITELLM_BASE_URL",
    "LITELLM_API_KEY",
    "MODEL_BUDGET_USD",
    "CONFIG_DIR",
    "RUNS_DIR",
    "FIXTURES_DIR",
)
_PRICING = """\
models:
  "<cheap-model-name>": { input_per_1m_usd: "1.00", output_per_1m_usd: "2.00" }
  "<strong-model-name>": { input_per_1m_usd: "3.00", output_per_1m_usd: "4.00" }
lambda_usd_per_gb_second: "0.0000166667"
lambda_usd_per_request: "0.0000002"
crustdata_usd_per_credit: "0.01"
"""
_ANSWER = '{"icp_fit": true, "reasons": ["fits"], "headcount_band": "201-500", "stage": "series_a"}'
_CACHE_PROPOSAL = json.dumps(
    {
        "lever": "cache_company_data",
        "new_value": True,
        "rationale": "a quarter of tasks repeat a domain",
        "predicted_cost_change_pct": -5.0,
        "risk": "low",
    }
)


def _write_workspace(root: Path, budget: str) -> None:
    """Write config, 32 fitting fixture companies, and a .env file under root."""
    config = root / "config"
    config.mkdir()
    shutil.copy(_REPO_CONFIG / "policy.yaml", config)
    shutil.copy(_REPO_CONFIG / "icp.yaml", config)
    (config / "pricing.yaml").write_text(_PRICING, encoding="utf-8")
    store = JsonFixtureStore(root / "fixtures")
    labels: dict[str, CompanyLabel] = {}
    for index in range(32):
        domain = f"c{index:02d}.example.com"
        raw = {
            "basic_info": {"primary_domain": domain},
            "headcount": {"total": 300},
            "funding": {"last_round_type": "series_a"},
            "hiring": {"openings_count": 5},
        }
        record = CompanyRecord(
            domain=domain,
            employee_count=300,
            funding_stage="series_a",
            total_funding_usd=None,
            engineering_open_roles=5,
            industry=None,
            headcount_growth_pct_6m=None,
        )
        store.save_fetch(domain, CompanyFetch(record=record, raw=raw, credits_used=Decimal(2)))
        split = Split.HELDOUT if index < 8 else Split.EVAL
        labels[domain] = CompanyLabel(expected_fit=True, difficulty=Difficulty.EASY, split=split)
    store.save_labels(labels)
    env = (
        "LITELLM_BASE_URL=https://llm.example.test/v1\n"
        "LITELLM_API_KEY=sk-test-only\n"
        f"MODEL_BUDGET_USD={budget}\n"
        "LITELLM_LICENSE=unrelated-value\n"
    )
    (root / ".env").write_text(env, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from an isolated directory with no settings in the process environment."""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _completion() -> httpx.Response:
    """Return a chat completion with 2000 prompt and 100 completion tokens."""
    body = {
        "choices": [{"message": {"content": _ANSWER}}],
        "usage": {"prompt_tokens": 2000, "completion_tokens": 100},
    }
    return httpx.Response(200, json=body)


@respx.mock
def test_eval_baseline_runs_end_to_end_and_stores_results(workspace: Path) -> None:
    """Three tasks call the endpoint with the .env key and land in runs/<id>/."""
    _write_workspace(workspace, budget="5")
    route = respx.post(_URL).mock(return_value=_completion())
    result = CliRunner().invoke(app, ["eval", "baseline", "--run-id", "t1", "--tasks", "3"])
    assert result.exit_code == 0, result.output
    assert "tasks: 3 of 3 completed, 0 with errors" in result.output
    assert "model 0.019200" in result.output
    assert route.call_count == 3
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer sk-test-only"
    assert json.loads(sent.content)["model"] == "<strong-model-name>"
    assert (workspace / "runs" / "t1" / "results_v1.jsonl").is_file()
    assert (workspace / "runs" / "t1" / "config_v1.json").is_file()
    assert "sk-test-only" not in result.output


@respx.mock
def test_dry_run_refuses_when_the_projection_exceeds_half_the_budget(workspace: Path) -> None:
    """160 planned tasks at 0.0064 USD need 1.024 USD; half of about 1.97 USD is too little."""
    _write_workspace(workspace, budget="2")
    respx.post(_URL).mock(return_value=_completion())
    result = CliRunner().invoke(app, ["dry-run", "--tasks", "5"])
    assert result.exit_code == 1
    assert "projected model usd for 160 tasks: 1.0240" in result.output
    assert "remaining model budget usd: 1.9680" in result.output


def _answer_or_propose(request: httpx.Request) -> httpx.Response:
    """Answer qualification prompts, and propose turning the cache on to the optimizer."""
    system = json.loads(request.content)["messages"][0]["content"]
    content = _CACHE_PROPOSAL if system.startswith("You tune") else _ANSWER
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 2000, "completion_tokens": 100},
    }
    return httpx.Response(200, json=body)


@respx.mock
def test_optimize_runs_one_auto_approved_iteration_end_to_end(workspace: Path) -> None:
    """The model's cache proposal is applied, re-run on the full workload, and kept."""
    _write_workspace(workspace, budget="5")
    route = respx.post(_URL).mock(side_effect=_answer_or_propose)
    result = CliRunner().invoke(
        app, ["optimize", "--run-id", "o1", "--iterations", "1", "--auto-approve"]
    )
    assert result.exit_code == 0, result.output
    assert "iteration 1: cache_company_data=true kept (guardrails passed)" in result.output
    assert "accepted config version: 2" in result.output
    assert route.call_count == 40 + 1 + 40
    run_dir = workspace / "runs" / "o1"
    assert (run_dir / "config_v2.json").is_file()
    assert (run_dir / "results_v2.jsonl").is_file()
    assert len((run_dir / "iterations.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    reported = CliRunner().invoke(app, ["report", "--run-id", "o1"])
    assert reported.exit_code == 0, reported.output
    assert "cost per successful task usd: v1 " in reported.output
    report = (run_dir / "report" / "report.md").read_text(encoding="utf-8")
    assert "| 1 | cache_company_data | true | approved (auto-approved) | yes |" in report
    assert (run_dir / "report" / "cfo_inputs.json").is_file()


def test_missing_settings_name_fields_without_values(workspace: Path) -> None:
    """Without .env or variables, the error lists the missing setting names only."""
    result = CliRunner().invoke(app, ["eval", "baseline", "--run-id", "t1"])
    assert result.exit_code == 2
    assert "litellm_api_key" in result.output
    assert "model_budget_usd" in result.output


def test_lambda_runner_is_wired_with_measured_infra(workspace: Path) -> None:
    """The Lambda runner adds the memory lever and measured infrastructure cost."""
    _write_workspace(workspace, budget="5")
    settings = EvalSettings(
        litellm_base_url="https://llm.example.test/v1",
        litellm_api_key=SecretStr("sk-test-only"),
        model_budget_usd=Decimal(5),
        aws_region="us-east-1",
    )
    with httpx.Client() as http:
        stack = build_eval_stack(settings, RunnerKind.LAMBDA, http)
    assert stack.capabilities.infra_source is InfraCostSource.MEASURED
    assert Lever.LAMBDA_MEMORY in stack.capabilities.levers
