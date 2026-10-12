"""Summarize a run by split and decide whether a candidate may replace the accepted config."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from costwise.domain.analysis import RunSummary, summarize
from costwise.domain.config import OptimizerConfig
from costwise.domain.cost import Money
from costwise.domain.guardrails import GuardrailPolicy, GuardrailResult, evaluate_guardrails
from costwise.domain.task import Split, TaskResult


@dataclass(frozen=True, slots=True)
class Standing:
    """A config with its EVAL and HELDOUT summaries."""

    config: OptimizerConfig
    eval_summary: RunSummary
    heldout_summary: RunSummary


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether a candidate was kept, why, and the evidence behind it."""

    accepted: bool
    reason: str
    standing: Standing | None = None
    guardrails: GuardrailResult | None = None
    budget_stop: bool = False


def split_summaries(results: Sequence[TaskResult]) -> tuple[RunSummary, RunSummary] | None:
    """Return EVAL and HELDOUT summaries, or None when either split has no successful task."""
    eval_results = [r for r in results if r.request.split is Split.EVAL]
    heldout_results = [r for r in results if r.request.split is Split.HELDOUT]
    groups = (eval_results, heldout_results)
    if not all(any(r.success for r in group) for group in groups):
        return None
    return summarize(eval_results), summarize(heldout_results)


def judge(
    results: Sequence[TaskResult],
    candidate: OptimizerConfig,
    requested: int,
    current: Standing,
    policy: GuardrailPolicy,
) -> Verdict:
    """Accept the candidate only if its run finished, every guardrail passed, and it saved.

    The saving is in cost per successful task over both splits, against ``current``.
    """
    if len(results) < requested:
        return Verdict(
            accepted=False, reason="budget stop during the candidate run", budget_stop=True
        )
    summaries = split_summaries(results)
    if summaries is None:
        return Verdict(accepted=False, reason="candidate had a split with no successful task")
    eval_summary, heldout_summary = summaries
    guardrails = evaluate_guardrails(
        current.eval_summary, eval_summary, heldout_summary, current.heldout_summary, policy
    )
    standing = Standing(candidate, eval_summary, heldout_summary)
    failed = [check.name for check in guardrails.checks if not check.passed]
    if failed:
        reason = f"guardrails failed: {', '.join(failed)}"
        return Verdict(False, reason, standing=standing, guardrails=guardrails)
    accepted, reason = _saving_decision(current, standing, policy.min_saving_pct)
    return Verdict(accepted, reason, standing=standing, guardrails=guardrails)


def _saving_decision(current: Standing, candidate: Standing, min_pct: float) -> tuple[bool, str]:
    """Keep only a candidate whose cost per successful task fell, by at least min_pct."""
    before, after = cost_per_success(current), cost_per_success(candidate)
    saving = (before - after) / before * 100 if before else Decimal(0)
    if saving > 0 and saving >= Decimal(str(min_pct)):
        return True, f"guardrails passed, cost per successful task -{saving:.1f}%"
    needed = f"at least a {min_pct:.1f}%" if min_pct > 0 else "a"
    return False, (
        f"guardrails passed but no saving: cost per successful task {before:.6f} -> "
        f"{after:.6f} USD; needs {needed} drop"
    )


def cost_per_success(standing: Standing) -> Money:
    """Return total cost over successful tasks across both splits."""
    summaries = (standing.eval_summary, standing.heldout_summary)
    total = sum((s.totals.total_usd for s in summaries), Decimal(0))
    successes = sum(g.successes for s in summaries for g in s.by_difficulty.values())
    return total / successes
