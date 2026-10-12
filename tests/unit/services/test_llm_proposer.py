"""Tests for the model-backed proposer."""

import json
import logging

import pytest

from costwise.domain.config import Lever
from costwise.domain.errors import BudgetExceededError
from costwise.domain.proposals import Proposal
from costwise.ports.llm import LLMRequest, LLMResponse, TokenUsage
from costwise.services.llm_proposer import (
    MAX_PROPOSAL_TOKENS,
    PROPOSER_PROMPT_VERSION,
    LLMProposer,
)
from tests.testing_fakes.fake_llm import FakeLLMClient
from tests.unit.domain.builders import make_config, make_summary

ALL_LEVERS = frozenset(Lever)
CACHE_ON = {
    "lever": "cache_company_data",
    "new_value": True,
    "rationale": "half the tasks repeat a domain",
    "predicted_cost_change_pct": -12.5,
    "risk": "low",
}


def _reply(text: str) -> LLMResponse:
    """Wrap text as a model response."""
    return LLMResponse(
        text=text,
        usage=TokenUsage(input_tokens=300, output_tokens=60),
        latency_ms=5,
        model="strong-model",
    )


def _replies(*bodies: dict[str, object] | str) -> FakeLLMClient:
    """Return a fake that answers with each body, JSON-encoding dicts."""
    texts = [body if isinstance(body, str) else json.dumps(body) for body in bodies]
    return FakeLLMClient([_reply(text) for text in texts])


def _propose(
    llm: FakeLLMClient,
    available: frozenset[Lever] = ALL_LEVERS,
    rejected: tuple[Proposal, ...] = (),
) -> Proposal | None:
    """Ask the proposer with the starting config and a plain summary."""
    proposer = LLMProposer(llm, "strong-model")
    return proposer.propose(make_config(), make_summary(1.0, 100), available, rejected)


def test_returns_a_valid_proposal_from_one_call() -> None:
    """A valid reply needs one deterministic call to the named model."""
    llm = _replies(CACHE_ON)

    proposal = _propose(llm)

    assert proposal == Proposal.model_validate(CACHE_ON)
    assert len(llm.requests) == 1
    request = llm.requests[0]
    assert request.model == "strong-model"
    assert request.temperature == 0.0
    assert request.max_output_tokens == MAX_PROPOSAL_TOKENS


def test_prompt_carries_bounds_and_evidence() -> None:
    """The prompts state lever bounds, the config, the summary, and the levers."""
    llm = _replies(CACHE_ON)

    _propose(llm, available=frozenset({Lever.CACHE, Lever.ROUTING}))

    request = llm.requests[0]
    assert "integer 0 to 5" in request.system
    assert "integer 64 to 1024" in request.system
    assert "256, 512, 1024, 2048" in request.system
    assert make_config().model_dump_json() in request.user
    assert make_summary(1.0, 100).model_dump_json() in request.user
    assert "Available levers: cache_company_data, routing" in request.user


def test_accepts_a_fenced_reply() -> None:
    """One surrounding code fence is tolerated."""
    llm = _replies(f"```json\n{json.dumps(CACHE_ON)}\n```")

    assert _propose(llm) is not None


def test_repairs_an_invalid_reply_once() -> None:
    """A malformed reply is sent back with the reason for one more try."""
    llm = _replies("not json", CACHE_ON)

    proposal = _propose(llm)

    assert proposal is not None
    assert len(llm.requests) == 2
    repair = llm.requests[1].user
    assert "Your previous reply was rejected: not a valid proposal object" in repair
    assert "not json" in repair


def test_repairs_an_unavailable_lever() -> None:
    """An unavailable lever is rejected twice and yields nothing."""
    llm = _replies(CACHE_ON, CACHE_ON)

    proposal = _propose(llm, available=frozenset({Lever.ROUTING}))

    assert proposal is None
    assert "lever is not available" in llm.requests[1].user


def test_repairs_a_no_op_change() -> None:
    """A value equal to the current config is sent back for repair."""
    no_op = {**CACHE_ON, "new_value": False}
    llm = _replies(no_op, CACHE_ON)

    proposal = _propose(llm)

    assert proposal is not None
    assert proposal.new_value is True
    assert "no actual change" in llm.requests[1].user


def test_repairs_a_rejected_repeat() -> None:
    """Rejected proposals are shown to the model and a repeat is sent back."""
    rejected = Proposal.model_validate(CACHE_ON)
    memory = {**CACHE_ON, "lever": "lambda_memory_mb", "new_value": 512}
    llm = _replies(CACHE_ON, memory)

    proposal = _propose(llm, rejected=(rejected,))

    assert proposal is not None
    assert proposal.lever is Lever.LAMBDA_MEMORY
    assert "rejected before" in llm.requests[1].user
    assert '"lever": "cache_company_data"' in llm.requests[0].user


def test_returns_none_after_a_failed_repair(caplog: pytest.LogCaptureFixture) -> None:
    """Two invalid replies give None and a warning, never a third call."""
    llm = _replies("{}", "{}")

    with caplog.at_level(logging.WARNING):
        proposal = _propose(llm)

    assert proposal is None
    assert len(llm.requests) == 2
    assert "invalid after repair" in caplog.text


def test_returns_none_when_the_model_call_fails(caplog: pytest.LogCaptureFixture) -> None:
    """A model error is logged and leaves the heuristic to answer."""
    llm = _replies()

    with caplog.at_level(logging.WARNING):
        proposal = _propose(llm)

    assert proposal is None
    assert "optimizer model call failed" in caplog.text


def test_budget_stop_propagates() -> None:
    """A budget stop is not swallowed."""

    def refuse(request: LLMRequest) -> LLMResponse:
        """Refuse every call at the budget stop line."""
        del request
        raise BudgetExceededError("stop line reached")

    with pytest.raises(BudgetExceededError):
        _propose(FakeLLMClient(refuse))


def test_logs_the_prompt_version(caplog: pytest.LogCaptureFixture) -> None:
    """Each proposal logs which prompt version produced it."""
    with caplog.at_level(logging.INFO):
        _propose(_replies(CACHE_ON))

    assert f"version={PROPOSER_PROMPT_VERSION}" in caplog.text
