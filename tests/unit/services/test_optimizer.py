"""Tests for choosing the next proposal."""

import logging
from collections.abc import Sequence

import pytest

from costwise.domain.analysis import RunSummary
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.services.optimizer import OptimizerService
from tests.unit.domain.builders import make_config, make_summary

ALL_LEVERS = frozenset(Lever)
CACHE_ON = Proposal(
    lever=Lever.CACHE,
    new_value=True,
    rationale="tasks repeat domains",
    predicted_cost_change_pct=-10.0,
    risk="low",
)
SMALLER_MEMORY = Proposal(
    lever=Lever.LAMBDA_MEMORY,
    new_value=512,
    rationale="memory looks oversized",
    predicted_cost_change_pct=-5.0,
    risk="medium",
)


class StubProposer:
    """Return a fixed proposal and record the rejected list it was given."""

    def __init__(self, proposal: Proposal | None) -> None:
        """Store the proposal to return."""
        self._proposal = proposal
        self.seen_rejected: list[list[Proposal]] = []

    def propose(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        rejected: Sequence[Proposal],
    ) -> Proposal | None:
        """Record rejected and return the fixed proposal."""
        del config, summary, available
        self.seen_rejected.append(list(rejected))
        return self._proposal


def _record(proposal: Proposal, *, accepted: bool) -> IterationRecord:
    """Return a past iteration for proposal."""
    return IterationRecord(
        iteration=1,
        proposal=proposal,
        decision=ApprovalDecision(approved=True, note=""),
        baseline_version=1,
        candidate_version=2,
        candidate_summary=None,
        guardrails=None,
        accepted=accepted,
        reason="",
    )


def _next(
    optimizer: OptimizerService,
    available: frozenset[Lever] = ALL_LEVERS,
    history: tuple[IterationRecord, ...] = (),
) -> Proposal | None:
    """Ask for the next proposal from the starting config."""
    return optimizer.next_proposal(make_config(), make_summary(1.0, 100), available, history)


def test_uses_the_model_proposal_first() -> None:
    """A valid model proposal wins without asking the heuristic."""
    llm, heuristic = StubProposer(CACHE_ON), StubProposer(SMALLER_MEMORY)

    assert _next(OptimizerService(llm, heuristic)) == CACHE_ON
    assert heuristic.seen_rejected == []


def test_falls_back_to_the_heuristic_when_the_model_has_nothing() -> None:
    """No model proposal means the heuristic answers."""
    optimizer = OptimizerService(StubProposer(None), StubProposer(SMALLER_MEMORY))

    assert _next(optimizer) == SMALLER_MEMORY


def test_discards_an_invalid_model_proposal(caplog: pytest.LogCaptureFixture) -> None:
    """An invalid proposal is logged and dropped, never returned."""
    optimizer = OptimizerService(StubProposer(CACHE_ON), StubProposer(SMALLER_MEMORY))

    with caplog.at_level(logging.WARNING):
        proposal = _next(optimizer, available=frozenset({Lever.LAMBDA_MEMORY}))

    assert proposal == SMALLER_MEMORY
    assert "discarded invalid proposal for cache_company_data" in caplog.text


def test_returns_none_when_no_proposal_is_usable() -> None:
    """With nothing valid from either proposer, there is no next step."""
    optimizer = OptimizerService(StubProposer(CACHE_ON), StubProposer(None))

    assert _next(optimizer, available=frozenset({Lever.ROUTING})) is None


def test_works_without_a_model_proposer() -> None:
    """The heuristic alone is enough to run the optimizer."""
    assert _next(OptimizerService(None, StubProposer(SMALLER_MEMORY))) == SMALLER_MEMORY


def test_passes_only_rejected_history_to_proposers() -> None:
    """Accepted iterations are not treated as rejected."""
    llm = StubProposer(None)
    history = (_record(CACHE_ON, accepted=False), _record(SMALLER_MEMORY, accepted=True))

    _next(OptimizerService(llm, StubProposer(None)), history=history)

    assert llm.seen_rejected == [[CACHE_ON]]


def test_discards_a_repeat_of_a_rejected_proposal(caplog: pytest.LogCaptureFixture) -> None:
    """A proposer that repeats a rejected change is overruled."""
    optimizer = OptimizerService(StubProposer(CACHE_ON), StubProposer(SMALLER_MEMORY))
    history = (_record(CACHE_ON, accepted=False),)

    with caplog.at_level(logging.WARNING):
        proposal = _next(optimizer, history=history)

    assert proposal == SMALLER_MEMORY
    assert "discarded repeated proposal for cache_company_data" in caplog.text
