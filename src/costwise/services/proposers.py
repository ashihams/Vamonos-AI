"""Deterministic rule-based proposer: the first matching, not-yet-rejected rule wins.

Predicted savings are upper bounds from the summary: the share of total cost the
lever touches, times the share of tasks or resources it changes.
"""

from collections.abc import Callable, Sequence
from decimal import Decimal

from costwise.domain.analysis import RunSummary
from costwise.domain.config import ALLOWED_MEMORY_MB, Lever, OptimizerConfig
from costwise.domain.icp import ICP_FIELDS
from costwise.domain.proposals import JsonValue, Proposal
from costwise.domain.task import ModelTier

OUTPUT_TOKEN_TIERS = (64, 128, 256, 512, 1024)
EASY_STRONG_SHARE = 0.10
LARGE_INPUT_TOKENS = 2_000
OUTPUT_HEADROOM = 0.5
MAX_MISSING_FIELDS_GTE = 5

_Rule = Callable[[OptimizerConfig, RunSummary], Proposal | None]


def is_rejected(proposal: Proposal, rejected: Sequence[Proposal]) -> bool:
    """Return whether the same lever and value were rejected before."""
    return any(
        old.lever is proposal.lever and old.new_value == proposal.new_value for old in rejected
    )


class HeuristicProposer:
    """Propose cache, routing, payload, output cap, then memory changes, in that order."""

    def propose(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        rejected: Sequence[Proposal],
    ) -> Proposal | None:
        """Return the first rule's proposal whose lever is available and not rejected."""
        rules: tuple[tuple[Lever, _Rule], ...] = (
            (Lever.CACHE, _enable_cache),
            (Lever.ROUTING, _route_easy_cheap),
            (Lever.PAYLOAD_FIELDS, _trim_payload),
            (Lever.MAX_OUTPUT_TOKENS, _lower_output_cap),
            (Lever.LAMBDA_MEMORY, _lower_memory),
        )
        for lever, rule in rules:
            if lever not in available:
                continue
            proposal = rule(config, summary)
            if proposal is not None and not is_rejected(proposal, rejected):
                return proposal
        return None


def _saving_pct(part: Decimal, summary: RunSummary, fraction: float) -> float:
    """Return minus the percentage of total cost in part, scaled by fraction."""
    total = summary.totals.total_usd
    if total <= 0:
        return 0.0
    return -round(float(part / total) * fraction * 100, 1)


def _enable_cache(config: OptimizerConfig, summary: RunSummary) -> Proposal | None:
    """Turn the company-data cache on when tasks repeat domains."""
    if config.cache_company_data or summary.repeat_rate <= 0:
        return None
    return Proposal(
        lever=Lever.CACHE,
        new_value=True,
        rationale=(
            f"{summary.repeat_rate:.0%} of tasks repeat a domain; a cache skips their data cost"
        ),
        predicted_cost_change_pct=_saving_pct(
            summary.totals.data_usd, summary, summary.repeat_rate
        ),
        risk="low",
    )


def _route_easy_cheap(config: OptimizerConfig, summary: RunSummary) -> Proposal | None:
    """Send easy tasks to the cheap tier, escalating one more missing field than before.

    Raising the missing-field threshold alone changes nothing while the default
    tier is strong, so a strong default is switched to cheap with near-threshold
    companies kept on the strong tier.
    """
    share = summary.easy_routed_strong / summary.n if summary.n else 0.0
    if share <= EASY_STRONG_SHARE:
        return None
    routing = config.routing
    to_cheap = routing.default_tier is ModelTier.STRONG
    gte = min(routing.strong_if_missing_fields_gte + 1, MAX_MISSING_FIELDS_GTE)
    if not to_cheap and gte == routing.strong_if_missing_fields_gte:
        return None
    value: dict[str, JsonValue] = {
        "default_tier": ModelTier.CHEAP.value,
        "strong_if_missing_fields_gte": gte,
        "strong_if_near_threshold": True if to_cheap else routing.strong_if_near_threshold,
    }
    return Proposal(
        lever=Lever.ROUTING,
        new_value=value,
        rationale=(
            f"{share:.0%} of tasks are easy but used the strong model; "
            "at most that share of model cost"
        ),
        predicted_cost_change_pct=_saving_pct(summary.totals.model_usd, summary, share),
        risk="medium",
    )


def _trim_payload(config: OptimizerConfig, summary: RunSummary) -> Proposal | None:
    """Send only the ICP fields when the full payload makes prompts large."""
    if config.payload_fields is not None or summary.avg_input_tokens <= LARGE_INPUT_TOKENS:
        return None
    fields: list[JsonValue] = list(ICP_FIELDS)
    return Proposal(
        lever=Lever.PAYLOAD_FIELDS,
        new_value=fields,
        rationale=(
            f"average input is {summary.avg_input_tokens:.0f} tokens with the full payload; "
            "the rule reads only three fields; at most the model cost"
        ),
        predicted_cost_change_pct=_saving_pct(summary.totals.model_usd, summary, 1.0),
        risk="medium",
    )


def _lower_output_cap(config: OptimizerConfig, summary: RunSummary) -> Proposal | None:
    """Step the output cap down one tier when answers use under half of it.

    Tokens are billed as used, so this bounds runaway answers rather than saving now.
    """
    cap = config.max_output_tokens
    lower = [tier for tier in OUTPUT_TOKEN_TIERS if tier < cap]
    if not lower or summary.avg_output_tokens >= OUTPUT_HEADROOM * cap:
        return None
    return Proposal(
        lever=Lever.MAX_OUTPUT_TOKENS,
        new_value=lower[-1],
        rationale=(
            f"answers average {summary.avg_output_tokens:.0f} of {cap} output tokens; "
            "a lower cap bounds runaway answers"
        ),
        predicted_cost_change_pct=0.0,
        risk="low",
    )


def _lower_memory(config: OptimizerConfig, summary: RunSummary) -> Proposal | None:
    """Step Lambda memory down to the next smaller allowed size."""
    current = config.lambda_memory_mb
    smaller = sorted(size for size in ALLOWED_MEMORY_MB if size < current)
    if not smaller:
        return None
    target = smaller[-1]
    return Proposal(
        lever=Lever.LAMBDA_MEMORY,
        new_value=target,
        rationale=f"try {target} MB instead of {current} MB; at most the matching infra cost",
        predicted_cost_change_pct=_saving_pct(
            summary.totals.infra_usd, summary, 1 - target / current
        ),
        risk="medium",
    )
