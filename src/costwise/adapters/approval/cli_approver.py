"""Approver that shows a proposal in the terminal and asks a human."""

import json
from collections.abc import Callable

import typer

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import ApprovalDecision, Proposal

YES = frozenset({"y", "yes"})
NO = frozenset({"n", "no"})


def _ask(prompt: str) -> str:
    """Read one line from the terminal, allowing an empty answer."""
    return str(typer.prompt(prompt, default="", show_default=False))


def proposal_lines(proposal: Proposal, evidence: RunSummary) -> list[str]:
    """Return the proposal and the key evidence numbers as display lines."""
    return [
        f"lever: {proposal.lever.value}",
        f"new value: {json.dumps(proposal.new_value)}",
        f"rationale: {proposal.rationale}",
        f"predicted cost change: {proposal.predicted_cost_change_pct:+.1f}%  risk: {proposal.risk}",
        f"evidence (EVAL, {evidence.n} tasks): success {evidence.success_rate:.1%}, "
        f"cost per successful task {evidence.cost_per_successful_task:.6f} usd, "
        f"p95 {evidence.p95_latency_ms} ms",
        f"cost usd: model {evidence.totals.model_usd:.6f}, infra {evidence.totals.infra_usd:.6f}, "
        f"data {evidence.totals.data_usd:.6f}",
    ]


class CliApprover:
    """Print the proposal, then read y or n and an optional note."""

    def __init__(
        self,
        ask: Callable[[str], str] = _ask,
        say: Callable[[str], None] = typer.echo,
    ) -> None:
        """Use ask to read answers and say to print lines."""
        self._ask = ask
        self._say = say

    def review(self, proposal: Proposal, evidence: RunSummary) -> ApprovalDecision:
        """Show the proposal and return the human's decision."""
        for line in proposal_lines(proposal, evidence):
            self._say(line)
        approved = self._yes_or_no()
        note = self._ask("note (optional)").strip()
        return ApprovalDecision(approved=approved, note=note)

    def _yes_or_no(self) -> bool:
        """Ask until the answer is y or n."""
        while True:
            answer = self._ask("apply this change? [y/n]").strip().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            self._say("please answer y or n")
