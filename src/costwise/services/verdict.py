"""Summarize a run by split and decide whether a candidate may replace the accepted config."""

from collections.abc import Sequence
from dataclasses import dataclass

from costwise.domain.analysis import RunSummary, summarize
from costwise.domain.config import OptimizerConfig
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
    """Accept the candidate only if its run finished and every guardrail passed."""
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
    failed = [check.name for check in guardrails.checks if not check.passed]
    reason = f"guardrails failed: {', '.join(failed)}" if failed else "guardrails passed"
    return Verdict(
        accepted=guardrails.passed,
        reason=reason,
        standing=Standing(candidate, eval_summary, heldout_summary),
        guardrails=guardrails,
    )
