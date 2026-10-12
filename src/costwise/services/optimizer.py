"""Choose the next proposal: the model first, then the heuristic, never an invalid one."""

import logging
from collections.abc import Sequence
from typing import Protocol

from costwise.domain.analysis import RunSummary
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import ConfigError
from costwise.domain.proposals import IterationRecord, Proposal, validate_proposal
from costwise.services.proposers import is_rejected

_LOG = logging.getLogger(__name__)


class Proposer(Protocol):
    """Suggests one lever change from an EVAL-split summary."""

    def propose(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        rejected: Sequence[Proposal],
    ) -> Proposal | None:
        """Return one proposal or None."""
        ...


class OptimizerService:
    """Try the model proposer, fall back to the heuristic, and validate whatever comes back.

    The summary must come from EVAL-split results only; held-out results never reach here.
    """

    def __init__(self, llm_proposer: Proposer | None, heuristic: Proposer) -> None:
        """Use llm_proposer first when given, then heuristic."""
        self._proposers: list[Proposer] = [heuristic]
        if llm_proposer is not None:
            self._proposers.insert(0, llm_proposer)

    def next_proposal(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        history: Sequence[IterationRecord],
    ) -> Proposal | None:
        """Return the first valid proposal not rejected in an earlier iteration, or None."""
        rejected = [record.proposal for record in history if not record.accepted]
        for proposer in self._proposers:
            proposal = proposer.propose(config, summary, available, rejected)
            if proposal is not None and _usable(proposal, config, available, rejected):
                return proposal
        return None


def _usable(
    proposal: Proposal,
    config: OptimizerConfig,
    available: frozenset[Lever],
    rejected: Sequence[Proposal],
) -> bool:
    """Return whether the proposal is valid now and was not rejected before."""
    try:
        validate_proposal(proposal, config, available)
    except ConfigError as exc:
        _LOG.warning("discarded invalid proposal for %s: %s", proposal.lever.value, exc)
        return False
    if is_rejected(proposal, rejected):
        _LOG.warning("discarded repeated proposal for %s", proposal.lever.value)
        return False
    return True
