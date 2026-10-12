"""Environment settings."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from costwise.settings import CrustdataSettings, EvalSettings

_REQUIRED = {
    "LITELLM_BASE_URL": "https://example.test/v1",
    "LITELLM_API_KEY": "sk-test-key",
    "NEATLOGS_API_KEY": "neat-test-key",
    "MODEL_BUDGET_USD": "12.50",
}


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the evaluation settings variables."""
    for name, value in _REQUIRED.items():
        monkeypatch.setenv(name, value)


def test_eval_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required keys, the budget, and defaults come from the environment; keys stay hidden."""
    _set_required(monkeypatch)
    settings = EvalSettings()
    assert settings.litellm_base_url == "https://example.test/v1"
    assert settings.litellm_api_key.get_secret_value() == "sk-test-key"
    assert settings.model_budget_usd == Decimal("12.50")
    assert settings.config_dir.as_posix() == "config"
    assert settings.runs_dir.as_posix() == "runs"
    rendered = repr(settings)
    assert "sk-test-key" not in rendered
    assert "neat-test-key" not in rendered


def test_eval_settings_reject_a_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing required variable fails validation."""
    _set_required(monkeypatch)
    monkeypatch.delenv("LITELLM_API_KEY")
    with pytest.raises(ValidationError):
        EvalSettings()


def test_crustdata_settings_need_only_the_crustdata_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture builds read the Crustdata key without the model or telemetry keys."""
    monkeypatch.setenv("CRUSTDATA_API_KEY", "crust-test-key")
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    settings = CrustdataSettings()
    assert settings.crustdata_api_key.get_secret_value() == "crust-test-key"
    assert "crust-test-key" not in repr(settings)
