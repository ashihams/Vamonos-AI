"""Tests for the rule-based proposer."""

from decimal import Decimal

import pytest

from costwise.domain.analysis import RunSummary
from costwise.domain.config import Lever, OptimizerConfig, RoutingPolicy
from costwise.domain.cost import CostBreakdown
from costwise.domain.icp import ICP_FIELDS
from costwise.domain.proposals import Proposal, validate_proposal
from costwise.domain.task import ModelTier
from costwise.services.proposers import HeuristicProposer, is_rejected
from tests.unit.domain.builders import make_config, make_summary

ALL_LEVERS = frozenset(Lever)
TOTALS = CostBreakdown(model_usd=Decimal("0.6"), infra_usd=Decimal("0.1"), data_usd=Decimal("0.3"))


def _summary(**update: object) -> RunSummary:
    """Return a summary with cost totals of 1 USD, tokens that trigger nothing, and update."""
    base = make_summary(1.0, 100).model_copy(
        update={"n": 10, "totals": TOTALS, "avg_output_tokens": 400.0}
    )
    return base.model_copy(update=update)


def _config(**update: object) -> OptimizerConfig:
    """Return the starting config with update applied."""
    return make_config().model_copy(update=update)


def _propose(
    config: OptimizerConfig,
    summary: RunSummary,
    available: frozenset[Lever] = ALL_LEVERS,
    rejected: tuple[Proposal, ...] = (),
) -> Proposal | None:
    """Run the heuristic and check that any proposal is valid."""
    proposal = HeuristicProposer().propose(config, summary, available, rejected)
    if proposal is not None:
        validate_proposal(proposal, config, available)
    return proposal


def test_enables_cache_when_domains_repeat() -> None:
    """Repeated domains turn the cache on, saving at most their share of data cost."""
    proposal = _propose(_config(), _summary(repeat_rate=0.5))

    assert proposal is not None
    assert proposal.lever is Lever.CACHE
    assert proposal.new_value is True
    assert proposal.predicted_cost_change_pct == pytest.approx(-15.0)
    assert proposal.risk == "low"


def test_routes_easy_tasks_cheap_from_a_strong_default() -> None:
    """A strong default flips to cheap, keeping near-threshold companies strong."""
    proposal = _propose(_config(), _summary(easy_routed_strong=5))

    assert proposal is not None
    assert proposal.lever is Lever.ROUTING
    assert proposal.new_value == {
        "default_tier": "cheap",
        "strong_if_missing_fields_gte": 1,
        "strong_if_near_threshold": True,
    }
    assert proposal.predicted_cost_change_pct == pytest.approx(-30.0)


def test_routing_from_a_cheap_default_raises_the_threshold_only() -> None:
    """A cheap default only escalates on one more missing field."""
    routing = RoutingPolicy(
        default_tier=ModelTier.CHEAP,
        strong_if_missing_fields_gte=2,
        strong_if_near_threshold=False,
    )

    proposal = _propose(_config(routing=routing), _summary(easy_routed_strong=5))

    assert proposal is not None
    assert proposal.new_value == {
        "default_tier": "cheap",
        "strong_if_missing_fields_gte": 3,
        "strong_if_near_threshold": False,
    }


def test_routing_at_the_highest_threshold_moves_on() -> None:
    """Routing that cannot change further proposes nothing."""
    routing = RoutingPolicy(
        default_tier=ModelTier.CHEAP,
        strong_if_missing_fields_gte=5,
        strong_if_near_threshold=False,
    )
    available = frozenset({Lever.ROUTING})

    assert _propose(_config(routing=routing), _summary(easy_routed_strong=5), available) is None


def test_routing_needs_more_than_a_tenth_of_tasks_easy_on_strong() -> None:
    """Exactly a tenth of easy tasks on the strong model is not enough."""
    available = frozenset({Lever.ROUTING})

    assert _propose(_config(), _summary(easy_routed_strong=1), available) is None


def test_trims_payload_to_icp_fields_when_inputs_are_large() -> None:
    """Large full payloads are cut to the fields the ICP rule reads."""
    proposal = _propose(_config(), _summary(avg_input_tokens=5_000.0))

    assert proposal is not None
    assert proposal.lever is Lever.PAYLOAD_FIELDS
    assert proposal.new_value == list(ICP_FIELDS)
    assert proposal.predicted_cost_change_pct == pytest.approx(-60.0)


def test_keeps_an_already_trimmed_payload() -> None:
    """A payload that is already a field list is left alone."""
    config = _config(payload_fields=ICP_FIELDS)
    available = frozenset({Lever.PAYLOAD_FIELDS})

    assert _propose(config, _summary(avg_input_tokens=5_000.0), available) is None


def test_lowers_output_cap_one_tier_when_answers_are_short() -> None:
    """Answers under half the cap step it down one tier, predicting no saving."""
    proposal = _propose(_config(), _summary(avg_output_tokens=100.0))

    assert proposal is not None
    assert proposal.lever is Lever.MAX_OUTPUT_TOKENS
    assert proposal.new_value == 256
    assert proposal.predicted_cost_change_pct == 0.0


def test_keeps_the_lowest_output_cap() -> None:
    """The smallest tier has nowhere lower to go."""
    config = _config(max_output_tokens=64)
    available = frozenset({Lever.MAX_OUTPUT_TOKENS})

    assert _propose(config, _summary(avg_output_tokens=1.0), available) is None


def test_lowers_memory_to_the_next_allowed_size() -> None:
    """Memory steps down one allowed size, saving at most that share of infra cost."""
    proposal = _propose(_config(), _summary())

    assert proposal is not None
    assert proposal.lever is Lever.LAMBDA_MEMORY
    assert proposal.new_value == 512
    assert proposal.predicted_cost_change_pct == pytest.approx(-5.0)


def test_returns_none_when_no_rule_applies() -> None:
    """With nothing to improve, the heuristic proposes nothing."""
    assert _propose(_config(lambda_memory_mb=256), _summary()) is None


def test_skips_unavailable_levers() -> None:
    """Rules for levers the runner lacks are skipped."""
    available = ALL_LEVERS - {Lever.CACHE, Lever.LAMBDA_MEMORY}

    assert _propose(_config(), _summary(repeat_rate=0.5), available) is None


def test_skips_rejected_proposals_for_the_next_rule() -> None:
    """A rejected proposal is not repeated; the next rule gets a turn."""
    summary = _summary(repeat_rate=0.5)
    first = _propose(_config(), summary)
    assert first is not None

    proposal = _propose(_config(), summary, rejected=(first,))

    assert proposal is not None
    assert proposal.lever is Lever.LAMBDA_MEMORY


def test_predicts_no_saving_when_nothing_was_spent() -> None:
    """A zero-cost run predicts a zero change instead of dividing by zero."""
    zero = CostBreakdown(model_usd=Decimal(0), infra_usd=Decimal(0), data_usd=Decimal(0))

    proposal = _propose(_config(), _summary(repeat_rate=0.5, totals=zero))

    assert proposal is not None
    assert proposal.predicted_cost_change_pct == 0.0


def test_is_rejected_matches_lever_and_value() -> None:
    """Only the same lever with the same value counts as a repeat."""
    old = Proposal(
        lever=Lever.CACHE,
        new_value=True,
        rationale="r",
        predicted_cost_change_pct=-1.0,
        risk="low",
    )

    assert is_rejected(old.model_copy(update={"rationale": "other"}), [old])
    assert not is_rejected(old.model_copy(update={"new_value": False}), [old])
    assert not is_rejected(old.model_copy(update={"lever": Lever.ROUTING}), [old])
