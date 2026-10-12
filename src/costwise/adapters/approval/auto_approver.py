"""Approver that approves every proposal, for tests and unattended runs."""

from costwise.domain.analysis import RunSummary
from costwise.domain.proposals import ApprovalDecision, Proposal

AUTO_APPROVED_NOTE = "auto-approved"


class AutoApprover:
    """Approve everything and say so in the note."""

    def review(self, proposal: Proposal, evidence: RunSummary) -> ApprovalDecision:
        """Return an approval tagged auto-approved."""
        del proposal, evidence
        return ApprovalDecision(approved=True, note=AUTO_APPROVED_NOTE)
