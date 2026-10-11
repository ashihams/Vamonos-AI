"""YAML loaders for prices, ICP rules, and policy."""

from decimal import Decimal
from pathlib import Path

import pytest

from costwise.adapters.storage.yaml_loaders import (
    load_guardrail_policy,
    load_icp_rule,
    load_initial_config,
    load_price_book,
    load_workload_policy,
)
from costwise.domain.errors import ConfigError
from costwise.domain.task import ModelTier

_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_example_configs_load() -> None:
    """The checked-in examples load with placeholder prices and the default config."""
    prices = load_price_book(_CONFIG / "pricing.yaml")
    rule = load_icp_rule(_CONFIG / "icp.yaml")
    policy = load_guardrail_policy(_CONFIG / "policy.yaml")
    config = load_initial_config(_CONFIG / "policy.yaml")
    assert prices.lambda_usd_per_gb_second == Decimal("0.0000166667")
    assert prices.lambda_usd_per_request == Decimal("0.0000002")
    assert prices.models["<cheap-model-name>"].input_per_1m_usd == Decimal("0.00")
    assert rule.min_employees == 50
    assert "series_a" in rule.allowed_stages
    assert policy.max_success_drop_pp == 2.0
    assert config.routing.default_tier is ModelTier.STRONG
    assert config.payload_fields is None
    assert config.lambda_memory_mb == 1024
    assert config.cache_company_data is False
    workload = load_workload_policy(_CONFIG / "policy.yaml")
    assert workload.n_requests == 40
    assert workload.repeat_ratio == 0.25
    assert workload.heldout_count == 8
    assert workload.seed == 42


def test_loader_errors_name_the_file_and_field(tmp_path: Path) -> None:
    """Unreadable, invalid, non-mapping, missing, and bad values name the file."""
    directory = tmp_path / "pricing.yaml"
    directory.mkdir()
    with pytest.raises(ConfigError, match="unreadable"):
        load_price_book(directory)

    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_price_book(broken)

    listing = tmp_path / "list.yaml"
    listing.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="document"):
        load_icp_rule(listing)

    policy = tmp_path / "policy.yaml"
    policy.write_text("workload: {n_requests: 1}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="guardrails"):
        load_guardrail_policy(policy)
    with pytest.raises(ConfigError, match="initial_config"):
        load_initial_config(policy)

    prices = tmp_path / "prices.yaml"
    prices.write_text(
        "models: {}\nlambda_usd_per_gb_second: 1.5\n"
        "lambda_usd_per_request: '0'\ncrustdata_usd_per_credit: '0'\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="lambda_usd_per_gb_second"):
        load_price_book(prices)
