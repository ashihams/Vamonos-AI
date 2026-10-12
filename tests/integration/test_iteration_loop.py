"""The approval loop on fakes: propose, approve, re-run, then keep or roll back."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import pytest

from costwise.adapters.approval.auto_approver import AutoApprover
from costwise.domain.analysis import RunSummary
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import BudgetExceededError, ConfigError, MissingStoreError
from costwise.domain.guardrails import GuardrailPolicy
from costwise.domain.labels import CompanyLabel
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.domain.task import (
    Difficulty,
    InfraCostSource,
    InvocationResult,
    ModelTier,
    QualificationRequest,
)
from costwise.ports.approval import Approver
from costwise.services.iteration import IterationDeciders, IterationService, IterationStores
from costwise.services.optimizer import OptimizerService, Proposer
from costwise.services.proposers import HeuristicProposer
from tests.testing_fakes import FakeRunner, InMemoryConfigStore, RecordingBudget, ScriptedApprover
from tests.testing_fakes.fake_runner import RunScript
from tests.unit.domain.builders import make_config
from tests.unit.eval_support import (
    LOCAL_LEVERS,
    EvalHarness,
    make_evaluation,
    make_invocation,
    make_labels,
    split_requests,
)

RUN = "loop"
LABELS = make_labels(8, heldout=(6, 7))
REQUESTS = split_requests(LABELS, 0, 1, 2, 0, 3, 4, 6, 5, 7, 6)
POLICY = GuardrailPolicy(max_success_drop_pp=2.0, p95_multiplier=1.25, budget_stop_fraction=0.8)
DECLINE = ApprovalDecision(approved=False, note="not now")
SMALLER_MEMORY = Proposal(
    lever=Lever.LAMBDA_MEMORY,
    new_value=512,
    rationale="memory looks oversized",
    predicted_cost_change_pct=-5.0,
    risk="medium",
)


def _answers(small_memory_misses_hard: bool = False) -> RunScript:
    """Answer from the labels; cheap routing, and optionally less memory, miss hard companies.

    Output tokens are a quarter of the cap and billing uses the configured memory, so the
    output-cap and memory levers change cost.
    """

    def respond(request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Return a correct answer unless this config misses hard companies."""
        label: CompanyLabel = LABELS[request.domain]
        cheap = config.routing.default_tier is ModelTier.CHEAP
        small = config.lambda_memory_mb < make_config().lambda_memory_mb
        misses_hard = cheap or (small_memory_misses_hard and small)
        wrong = misses_hard and label.difficulty is Difficulty.HARD
        invocation = make_invocation(request, label.expected_fit != wrong)
        call = invocation.calls[0].model_copy(
            update={"output_tokens": config.max_output_tokens // 4}
        )
        return invocation.model_copy(
            update={"calls": (call,), "billed_ms": 100, "memory_mb": config.lambda_memory_mb}
        )

    return respond


class FixedProposer:
    """Always propose the same change."""

    def __init__(self, proposal: Proposal) -> None:
        """Store the proposal."""
        self._proposal = proposal

    def propose(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        rejected: Sequence[Proposal],
    ) -> Proposal | None:
        """Return the stored proposal."""
        del config, summary, available, rejected
        return self._proposal


@dataclass
class Loop:
    """The loop and the fakes it runs on."""

    service: IterationService
    harness: EvalHarness
    runner: FakeRunner
    configs: InMemoryConfigStore


def _loop(
    approver: Approver,
    script: RunScript | None = None,
    levers: frozenset[Lever] = LOCAL_LEVERS,
    budget: RecordingBudget | None = None,
    llm_proposer: Proposer | None = None,
) -> Loop:
    """Wire the loop over in-memory stores with the heuristic as the fallback proposer."""
    runner = FakeRunner(levers, InfraCostSource.MODELED, script or _answers())
    harness = make_evaluation(runner, LABELS, budget)
    configs = InMemoryConfigStore()
    optimizer = OptimizerService(llm_proposer, HeuristicProposer())
    service = IterationService(
        harness.service,
        runner,
        IterationDeciders(optimizer, approver, POLICY),
        IterationStores(harness.store, configs, harness.telemetry),
        harness.budget,
    )
    return Loop(service, harness, runner, configs)


def _run(loop: Loop, iterations: int = 3) -> list[IterationRecord]:
    """Run the loop from the starting config over the whole workload."""
    return loop.service.run(RUN, make_config(), REQUESTS, iterations)


def test_loop_keeps_cache_rolls_back_routing_and_keeps_a_lower_cap() -> None:
    """The cheap-routing candidate misses hard companies and is rolled back; the rest stick."""
    loop = _loop(AutoApprover())

    records = _run(loop)

    assert [(r.proposal.lever, r.accepted) for r in records] == [
        (Lever.CACHE, True),
        (Lever.ROUTING, False),
        (Lever.MAX_OUTPUT_TOKENS, True),
    ]
    assert [(r.baseline_version, r.candidate_version) for r in records] == [(1, 2), (2, 3), (2, 4)]
    assert records[1].reason == "guardrails failed: eval_success, heldout_success"
    assert records[0].decision.note == "auto-approved"
    final = loop.configs.load(RUN, 4)
    assert final.cache_company_data is True
    assert final.max_output_tokens == 256
    assert final.routing == make_config().routing
    assert loop.harness.store.load_iterations(RUN) == records
    assert [record for _, record in loop.harness.telemetry.iterations] == records
    assert [version for _, version, _ in loop.harness.telemetry.summaries] == [1, 2, 3, 4]
    assert loop.harness.telemetry.flushed
    assert loop.runner.applied == []


def test_cache_lever_cuts_data_cost() -> None:
    """Two repeated domains stop paying for company data once the cache is on."""
    loop = _loop(AutoApprover())

    _run(loop, iterations=1)

    store = loop.harness.store
    before = sum(r.costs.data_usd for r in store.load_results(RUN, 1))
    after = sum(r.costs.data_usd for r in store.load_results(RUN, 2))
    assert (before, after) == (Decimal("0.20"), Decimal("0.16"))


def test_stops_after_two_consecutive_rejections() -> None:
    """Declined proposals are recorded, never run, and two in a row end the loop."""
    approver = ScriptedApprover([DECLINE, DECLINE, DECLINE])
    loop = _loop(approver)

    records = _run(loop)

    assert [(r.proposal.lever, r.reason) for r in records] == [
        (Lever.CACHE, "rejected by approver"),
        (Lever.ROUTING, "rejected by approver"),
    ]
    assert all(r.candidate_version is None and r.guardrails is None for r in records)
    assert len(approver.reviews) == 2
    assert len(loop.runner.runs) == len(REQUESTS)
    with pytest.raises(MissingStoreError):
        loop.configs.load(RUN, 2)


def test_budget_stop_during_a_candidate_run_ends_the_loop() -> None:
    """A candidate cut short by the budget is recorded as not accepted and the loop stops."""
    loop = _loop(AutoApprover(), budget=RecordingBudget(allowed_checks=15))

    records = _run(loop)

    assert len(records) == 1
    assert not records[0].accepted
    assert records[0].reason == "budget stop during the candidate run"
    assert records[0].candidate_summary is None
    assert loop.harness.telemetry.flushed


def test_budget_stop_before_an_iteration_returns_what_exists() -> None:
    """With the budget spent on the baseline, no iteration starts."""
    loop = _loop(AutoApprover(), budget=RecordingBudget(allowed_checks=len(REQUESTS)))

    assert _run(loop) == []


def test_budget_stop_during_the_baseline_is_an_error() -> None:
    """There is nothing to optimize against when the baseline is incomplete."""
    loop = _loop(AutoApprover(), budget=RecordingBudget(allowed_checks=5))

    with pytest.raises(BudgetExceededError, match="baseline"):
        _run(loop)
    assert loop.harness.telemetry.flushed


def test_reuses_a_stored_baseline() -> None:
    """A baseline already stored for version 1 is not run again."""
    loop = _loop(AutoApprover())
    loop.configs.save(RUN, make_config())
    loop.harness.service.evaluate(RUN, make_config(), REQUESTS)
    baseline_runs = len(loop.runner.runs)

    _run(loop, iterations=1)

    assert len(loop.runner.runs) == baseline_runs + len(REQUESTS)


def test_refuses_a_stored_baseline_over_other_tasks() -> None:
    """A partial stored baseline cannot be compared with full candidate runs."""
    loop = _loop(AutoApprover())
    loop.configs.save(RUN, make_config())
    loop.harness.service.evaluate(RUN, make_config(), REQUESTS[:5])

    with pytest.raises(ConfigError, match="does not cover the workload"):
        _run(loop)


def test_refuses_bad_arguments_and_reused_runs() -> None:
    """Zero iterations, a workload without held-out tasks, and a reused run id are refused."""
    loop = _loop(AutoApprover())
    with pytest.raises(ConfigError, match="at least 1"):
        _run(loop, iterations=0)
    with pytest.raises(ConfigError, match="HELDOUT"):
        loop.service.run("eval-only", make_config(), split_requests(LABELS, 0, 1), 1)
    _run(loop, iterations=1)
    with pytest.raises(ConfigError, match="already has iterations"):
        _run(loop, iterations=1)


def test_stops_when_nothing_can_be_proposed() -> None:
    """With no levers available there is no proposal and no candidate run."""
    loop = _loop(AutoApprover(), levers=frozenset())

    assert _run(loop) == []
    assert len(loop.runner.runs) == len(REQUESTS)


def test_candidate_without_a_successful_split_is_rolled_back() -> None:
    """A candidate that gets every task wrong has no summary and is not kept."""

    def all_wrong_with_cache(
        request: QualificationRequest, config: OptimizerConfig
    ) -> InvocationResult:
        """Answer wrongly for every company once the cache is on."""
        expected = LABELS[request.domain].expected_fit
        return make_invocation(request, expected != config.cache_company_data)

    loop = _loop(AutoApprover(), script=all_wrong_with_cache)

    records = _run(loop, iterations=1)

    assert records[0].reason == "candidate had a split with no successful task"
    assert records[0].guardrails is None


def test_memory_change_applies_infra_warms_up_and_rolls_back() -> None:
    """Less memory misses hard companies, so the old memory setting is restored."""
    loop = _loop(
        AutoApprover(),
        script=_answers(small_memory_misses_hard=True),
        levers=LOCAL_LEVERS | {Lever.LAMBDA_MEMORY},
        llm_proposer=FixedProposer(SMALLER_MEMORY),
    )

    records = _run(loop, iterations=1)

    assert not records[0].accepted
    assert [config.lambda_memory_mb for config in loop.runner.applied] == [512, 1024]
    assert len(loop.runner.runs) == 2 * len(REQUESTS) + 3


def test_kept_memory_change_is_not_rolled_back() -> None:
    """A memory change that passes the guardrails stays applied."""
    loop = _loop(
        AutoApprover(),
        levers=LOCAL_LEVERS | {Lever.LAMBDA_MEMORY},
        llm_proposer=FixedProposer(SMALLER_MEMORY),
    )

    records = _run(loop, iterations=1)

    assert records[0].accepted
    assert [config.lambda_memory_mb for config in loop.runner.applied] == [512]
