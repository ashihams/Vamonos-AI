"""Proposal validation and application."""

import pytest
from pydantic import ValidationError

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import ConfigError
from costwise.domain.proposals import (
    ApprovalDecision,
    IterationRecord,
    Proposal,
    apply_proposal,
    validate_proposal,
)
from costwise.domain.task import ModelTier
from tests.unit.domain.builders import make_config, make_summary

_ALL = frozenset(Lever)


def _proposal(lever: Lever, new_value: object) -> Proposal:
    """Build a low-risk proposal for one lever."""
    return Proposal(
        lever=lever,
        new_value=new_value,
        rationale="lower cost",
        predicted_cost_change_pct=-10.0,
        risk="low",
    )


def _routing(tier: str, missing: int, near: bool) -> dict[str, object]:
    """Build a routing JSON object."""
    return {
        "default_tier": tier,
        "strong_if_missing_fields_gte": missing,
        "strong_if_near_threshold": near,
    }


def test_apply_changes_routing_only() -> None:
    """Routing replacement bumps the version and leaves every other lever alone."""
    current = make_config()
    proposal = _proposal(Lever.ROUTING, _routing("cheap", 2, True))
    validate_proposal(proposal, current, _ALL)
    updated = apply_proposal(current, proposal)
    assert updated.version == 2
    assert updated.routing.default_tier is ModelTier.CHEAP
    assert updated.routing.strong_if_missing_fields_gte == 2
    assert updated.routing.strong_if_near_threshold is True
    assert updated.cheap_model == current.cheap_model
    assert updated.payload_fields is None
    assert updated.max_output_tokens == current.max_output_tokens
    assert updated.cache_company_data is False
    assert updated.lambda_memory_mb == current.lambda_memory_mb


@pytest.mark.parametrize(
    ("lever", "new_value", "field_name", "expected"),
    [
        (
            Lever.PAYLOAD_FIELDS,
            ["employee_count", "domain"],
            "payload_fields",
            ("employee_count", "domain"),
        ),
        (Lever.PAYLOAD_FIELDS, None, "payload_fields", None),
        (Lever.MAX_OUTPUT_TOKENS, 64, "max_output_tokens", 64),
        (Lever.MAX_OUTPUT_TOKENS, 1024, "max_output_tokens", 1024),
        (Lever.CACHE, True, "cache_company_data", True),
        (Lever.LAMBDA_MEMORY, 256, "lambda_memory_mb", 256),
    ],
)
def test_apply_changes_exactly_one_lever(
    lever: Lever,
    new_value: object,
    field_name: str,
    expected: object,
) -> None:
    """A valid proposal changes one field and increments the version."""
    current = make_config()
    if lever is Lever.PAYLOAD_FIELDS and new_value is None:
        current = current.model_copy(update={"payload_fields": ("industry",)})
    proposal = _proposal(lever, new_value)
    validate_proposal(proposal, current, _ALL)
    updated = apply_proposal(current, proposal)
    assert getattr(updated, field_name) == expected
    assert updated.version == current.version + 1
    for name in OptimizerConfig.model_fields:
        if name in {field_name, "version"}:
            continue
        assert getattr(updated, name) == getattr(current, name)


def test_validate_rejects_unavailable_lever() -> None:
    """A lever the runner cannot change is rejected."""
    proposal = _proposal(Lever.LAMBDA_MEMORY, 256)
    with pytest.raises(ConfigError, match="lever is not available"):
        validate_proposal(proposal, make_config(), frozenset({Lever.CACHE}))


@pytest.mark.parametrize(
    ("lever", "new_value"),
    [
        (Lever.ROUTING, _routing("strong", 0, False)),
        (Lever.PAYLOAD_FIELDS, None),
        (Lever.MAX_OUTPUT_TOKENS, 512),
        (Lever.CACHE, False),
        (Lever.LAMBDA_MEMORY, 1024),
    ],
)
def test_validate_rejects_no_actual_change(lever: Lever, new_value: object) -> None:
    """A proposal that leaves the lever as it is does not apply."""
    with pytest.raises(ConfigError, match="no actual change"):
        validate_proposal(_proposal(lever, new_value), make_config(), _ALL)


@pytest.mark.parametrize(
    ("lever", "new_value", "match"),
    [
        (Lever.ROUTING, ["cheap"], "routing value must be an object"),
        (Lever.ROUTING, _routing("cheap", True, False), "must be an integer"),
        (Lever.ROUTING, _routing("cheap", 6, False), "routing value is invalid"),
        (Lever.ROUTING, {"default_tier": "cheap"}, "routing value is invalid"),
        (Lever.PAYLOAD_FIELDS, "employee_count", "list of field names"),
        (Lever.PAYLOAD_FIELDS, ["hiring"], "unknown payload fields"),
        (Lever.PAYLOAD_FIELDS, ["domain", "domain"], "duplicates"),
        (Lever.PAYLOAD_FIELDS, ["domain", 1], "list of field names"),
        (Lever.MAX_OUTPUT_TOKENS, True, "expected an integer"),
        (Lever.MAX_OUTPUT_TOKENS, 1.5, "expected an integer"),
        (Lever.MAX_OUTPUT_TOKENS, 63, "between 64 and 1024"),
        (Lever.MAX_OUTPUT_TOKENS, 1025, "between 64 and 1024"),
        (Lever.CACHE, 1, "expected a boolean"),
        (Lever.LAMBDA_MEMORY, True, "expected an integer"),
        (Lever.LAMBDA_MEMORY, 128, "not an allowed size"),
        (Lever.LAMBDA_MEMORY, 300, "not an allowed size"),
    ],
)
def test_validate_rejects_out_of_bounds(lever: Lever, new_value: object, match: str) -> None:
    """Out-of-bounds values raise ConfigError before any comparison."""
    with pytest.raises(ConfigError, match=match):
        validate_proposal(_proposal(lever, new_value), make_config(), _ALL)


def test_apply_rejects_invalid_value() -> None:
    """Applying a bad value raises ConfigError."""
    with pytest.raises(ConfigError):
        apply_proposal(make_config(), _proposal(Lever.CACHE, "yes"))


def test_proposal_rejects_non_json_values() -> None:
    """Sets and non-string object keys are not JSON values."""
    with pytest.raises(ValidationError):
        _proposal(Lever.CACHE, {"not", "json"})
    with pytest.raises(ValidationError):
        _proposal(Lever.ROUTING, {1: "cheap"})


def test_proposal_rejects_unknown_risk() -> None:
    """Risk is one of low, medium, or high."""
    with pytest.raises(ValidationError):
        Proposal(
            lever=Lever.CACHE,
            new_value=True,
            rationale="lower cost",
            predicted_cost_change_pct=-5.0,
            risk="extreme",
        )


def test_iteration_record_round_trip() -> None:
    """An iteration record keeps the proposal, decision, and optional results."""
    proposal = _proposal(Lever.CACHE, True)
    decision = ApprovalDecision(approved=True, note="ship it")
    record = IterationRecord(
        iteration=1,
        proposal=proposal,
        decision=decision,
        baseline_version=1,
        candidate_version=2,
        candidate_summary=make_summary(1.0, 80),
        guardrails=None,
        accepted=True,
        reason="guardrails passed",
    )
    restored = IterationRecord.model_validate(record.model_dump())
    assert restored == record
    assert restored.decision.note == "ship it"
