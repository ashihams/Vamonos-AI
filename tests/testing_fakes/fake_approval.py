"""Approver that replays scripted decisions."""

from collections.abc import Sequence

from costwise.domain.analysis import RunSummary
from costwise.domain.errors import CostwiseError
from costwise.domain.proposals import ApprovalDecision, Proposal


class ScriptedApprover:
    """Return decisions in order and record each review."""

    def __init__(self, decisions: Sequence[ApprovalDecision]) -> None:
        """Copy the decision list and start an empty review log."""
        self._decisions = list(decisions)
        self.reviews: list[tuple[Proposal, RunSummary]] = []

    def review(self, proposal: Proposal, evidence: RunSummary) -> ApprovalDecision:
        """Record the review and return the next decision."""
        self.reviews.append((proposal, evidence))
        if not self._decisions:
            raise CostwiseError("no scripted decision")
        return self._decisions.pop(0)
