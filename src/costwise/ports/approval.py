"""Port for approving one optimizer proposal."""

from typing import Protocol

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import ApprovalDecision, Proposal


class Approver(Protocol):
    """Decides whether one proposal may be applied."""

    def review(self, proposal: Proposal, evidence: RunSummary) -> ApprovalDecision:
        """Return the decision for this proposal and the evidence shown with it."""
        ...
