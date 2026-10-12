"""Payload, routing, prompt, and parsing services."""

import json
import logging

import pytest

from costwise.domain.company import COMPANY_FIELD_NAMES
from costwise.domain.config import RoutingPolicy
from costwise.domain.errors import ParseError
from costwise.domain.task import ModelTier
from costwise.services.parsing import ParsingService
from costwise.services.payload import PayloadService, normalized_fields
from costwise.services.prompt import PROMPT_VERSION, PromptService
from costwise.services.routing import RoutingService
from tests.unit.domain.builders import make_company, make_rule

_ANSWER = '{"icp_fit": true, "reasons": ["fits"], "headcount_band": "201-500", "stage": "series_a"}'


def _policy(missing: int = 0, near: bool = False) -> RoutingPolicy:
    """Return a cheap-by-default policy with the given escalation rules."""
    return RoutingPolicy(
        default_tier=ModelTier.CHEAP,
        strong_if_missing_fields_gte=missing,
        strong_if_near_threshold=near,
    )


def test_trim_returns_raw_for_none_and_listed_fields_otherwise() -> None:
    """None sends the provider payload; a list sends those normalized fields in order."""
    record = make_company(300, "series_a", 12)
    raw = {"basic_info": {"name": "Example"}, "headcount": {"total": 300}}
    payloads = PayloadService()
    assert payloads.trim(record, raw, None) == raw
    trimmed = payloads.trim(record, raw, ("funding_stage", "employee_count"))
    assert list(trimmed) == ["funding_stage", "employee_count"]
    assert trimmed == {"funding_stage": "series_a", "employee_count": 300}
    assert set(normalized_fields(record)) == COMPANY_FIELD_NAMES


def test_estimate_tokens_is_characters_over_four() -> None:
    """The estimate is a floor of length / 4."""
    assert PayloadService().estimate_tokens("x" * 41) == 10


def test_routing_escalates_by_missing_fields_and_near_threshold() -> None:
    """Missing inputs and near-threshold values go strong only when the policy says so."""
    router = RoutingService()
    rule = make_rule()
    clear = make_company(300, "series_a", 20)
    two_missing = make_company(300, None, None)
    near_max = make_company(995, "series_a", 20)
    assert router.choose(clear, _policy(missing=1, near=True), rule) is ModelTier.CHEAP
    assert router.choose(two_missing, _policy(missing=2), rule) is ModelTier.STRONG
    assert router.choose(two_missing, _policy(missing=3), rule) is ModelTier.CHEAP
    assert router.choose(two_missing, _policy(missing=0), rule) is ModelTier.CHEAP
    assert router.choose(near_max, _policy(near=True), rule) is ModelTier.STRONG
    assert router.choose(near_max, _policy(near=False), rule) is ModelTier.CHEAP


def test_prompt_states_rule_and_embeds_payload(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The system prompt carries the thresholds and keys; the user prompt carries the JSON."""
    monkeypatch.setattr(logging.getLogger("costwise"), "propagate", True)
    with caplog.at_level(logging.INFO, logger="costwise.services.prompt"):
        system, user = PromptService().build({"employee_count": 300}, make_rule())
    assert "between 50 and 1000 inclusive" in system
    assert "series_a, series_b" in system
    assert "at least 10" in system
    for key in ("icp_fit", "reasons", "headcount_band", "stage"):
        assert f'"{key}"' in system
    assert json.loads(user.split("\n", 1)[1]) == {"employee_count": 300}
    assert PROMPT_VERSION in caplog.text


def test_parse_accepts_plain_and_fenced_json() -> None:
    """Bare JSON and one json code fence both parse to the same answer."""
    parser = ParsingService()
    plain = parser.parse(_ANSWER)
    assert plain.icp_fit is True
    assert plain.reasons == ("fits",)
    assert parser.parse(f"```json\n{_ANSWER}\n```") == plain
    assert parser.parse(f"  ```\n{_ANSWER}```  ") == plain


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "Sure! " + _ANSWER,
        '{"icp_fit": "yes", "reasons": [], "headcount_band": null, "stage": null}',
        '{"icp_fit": true, "reasons": []}',
        '{"icp_fit": true, "reasons": [], "headcount_band": null, "stage": null, "extra": 1}',
        "[]",
    ],
)
def test_parse_rejects_anything_but_the_schema(text: str) -> None:
    """Prose, wrong types, missing keys, extra keys, and non-objects raise ParseError."""
    with pytest.raises(ParseError, match="not a valid qualification"):
        ParsingService().parse(text)
