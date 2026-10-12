"""Propose, approve, apply, re-run, check guardrails, then keep or roll back."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import BudgetExceededError, ConfigError, MissingStoreError
from costwise.domain.guardrails import GuardrailPolicy
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal, apply_proposal
from costwise.domain.task import QualificationRequest
from costwise.ports.approval import Approver
from costwise.ports.budget import BudgetGuard
from costwise.ports.runner import TaskRunner
from costwise.ports.storage import ConfigStore, RunStore
from costwise.ports.telemetry import TelemetrySink
from costwise.services.evaluation import EvaluationService
from costwise.services.history import earlier_rejections
from costwise.services.optimizer import OptimizerService
from costwise.services.verdict import Standing, Verdict, judge, split_summaries

MAX_CONSECUTIVE_REJECTIONS = 2
WARM_UP_INVOCATIONS = 3

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IterationDeciders:
    """Who proposes, who approves, and the gates a candidate must pass."""

    optimizer: OptimizerService
    approver: Approver
    policy: GuardrailPolicy


@dataclass(frozen=True, slots=True)
class IterationStores:
    """Where configs, results, iteration records, and telemetry go."""

    runs: RunStore
    configs: ConfigStore
    telemetry: TelemetrySink


@dataclass(frozen=True, slots=True)
class _Attempt:
    """One proposal and the decision on it."""

    number: int
    proposal: Proposal
    decision: ApprovalDecision


@dataclass(slots=True)
class _Loop:
    """The accepted standing, the next free version, and what happened so far."""

    current: Standing
    next_version: int
    records: list[IterationRecord]
    earlier: tuple[Proposal, ...] = ()
    rejections: int = 0


class IterationService:
    """Improve the config one approved, guardrail-checked lever change at a time."""

    def __init__(
        self,
        evaluation: EvaluationService,
        runner: TaskRunner,
        deciders: IterationDeciders,
        stores: IterationStores,
        budget: BudgetGuard,
    ) -> None:
        """Wire evaluation, the runner, the deciders, the stores, and the budget guard."""
        self._evaluation = evaluation
        self._runner = runner
        self._deciders = deciders
        self._stores = stores
        self._budget = budget

    def run(
        self,
        run_id: str,
        start: OptimizerConfig,
        requests: Sequence[QualificationRequest],
        iterations: int,
    ) -> list[IterationRecord]:
        """Run up to iterations cycles from the stored or a fresh baseline; flush telemetry."""
        if iterations < 1:
            raise ConfigError("iterations must be at least 1")
        if self._stores.runs.load_iterations(run_id):
            raise ConfigError(f"run {run_id} already has iterations; use a new run id")
        try:
            loop = _Loop(
                self._baseline(run_id, start, requests),
                start.version + 1,
                [],
                earlier_rejections(self._stores.runs, self._stores.configs, run_id, start),
            )
            self._loop(run_id, loop, requests, iterations)
            return loop.records
        finally:
            self._stores.telemetry.flush()

    def _baseline(
        self, run_id: str, start: OptimizerConfig, requests: Sequence[QualificationRequest]
    ) -> Standing:
        """Load the stored baseline for start's version, or evaluate it now."""
        try:
            config = self._stores.configs.load(run_id, start.version)
            results = self._stores.runs.load_results(run_id, start.version)
        except MissingStoreError:
            config = start
            self._stores.configs.save(run_id, start)
            results = self._evaluation.evaluate(run_id, start, requests)
            if len(results) < len(requests):
                raise BudgetExceededError("the budget stopped the baseline run") from None
        if {r.request.task_id for r in results} != {r.task_id for r in requests}:
            raise ConfigError("the stored baseline does not cover the workload; use a new run id")
        summaries = split_summaries(results)
        if summaries is None:
            raise ConfigError("the baseline needs a successful EVAL and a successful HELDOUT task")
        self._stores.telemetry.record_summary(run_id, config.version, summaries[0])
        return Standing(config, *summaries)

    def _loop(
        self,
        run_id: str,
        loop: _Loop,
        requests: Sequence[QualificationRequest],
        iterations: int,
    ) -> None:
        """Iterate until the limit, no proposal, two rejections in a row, or a budget stop."""
        for number in range(1, iterations + 1):
            if loop.rejections >= MAX_CONSECUTIVE_REJECTIONS:
                _LOG.info("stopping after %d consecutive rejections", loop.rejections)
                return
            try:
                self._budget.assert_can_spend()
                outcome = self._iterate(run_id, number, loop, requests)
            except BudgetExceededError as exc:
                _LOG.warning("budget stop before iteration %d finished: %s", number, exc)
                return
            if outcome is None:
                _LOG.info("stopping: no usable proposal for iteration %d", number)
                return
            self._keep(run_id, loop, *outcome)
            if outcome[1].budget_stop:
                return

    def _iterate(
        self,
        run_id: str,
        number: int,
        loop: _Loop,
        requests: Sequence[QualificationRequest],
    ) -> tuple[IterationRecord, Verdict] | None:
        """Propose and approve one change, then verify it unless the approver said no."""
        current = loop.current
        proposal = self._deciders.optimizer.next_proposal(
            current.config,
            current.eval_summary,
            self._runner.capabilities().levers,
            loop.records,
            loop.earlier,
        )
        if proposal is None:
            return None
        attempt = _Attempt(
            number, proposal, self._deciders.approver.review(proposal, current.eval_summary)
        )
        if not attempt.decision.approved:
            verdict = Verdict(accepted=False, reason="rejected by approver")
            return _record(attempt, current.config.version, None, verdict), verdict
        candidate = apply_proposal(current.config, proposal).model_copy(
            update={"version": loop.next_version}
        )
        loop.next_version += 1
        verdict = self._verify(run_id, candidate, proposal.lever, current, requests)
        return _record(attempt, current.config.version, candidate.version, verdict), verdict

    def _verify(
        self,
        run_id: str,
        candidate: OptimizerConfig,
        lever: Lever,
        current: Standing,
        requests: Sequence[QualificationRequest],
    ) -> Verdict:
        """Run the candidate and judge it, restoring the infrastructure unless it was kept."""
        self._stores.configs.save(run_id, candidate)
        infra_changed = lever is Lever.LAMBDA_MEMORY
        verdict: Verdict | None = None
        try:
            if infra_changed:
                self._runner.apply_infra(candidate)
                for request in requests[:WARM_UP_INVOCATIONS]:
                    self._runner.run(request, candidate)
            results = self._evaluation.evaluate(run_id, candidate, requests)
            verdict = judge(results, candidate, len(requests), current, self._deciders.policy)
        finally:
            if infra_changed and (verdict is None or not verdict.accepted):
                self._runner.apply_infra(current.config)
        if verdict.standing is not None:
            summary = verdict.standing.eval_summary
            self._stores.telemetry.record_summary(run_id, candidate.version, summary)
        return verdict

    def _keep(self, run_id: str, loop: _Loop, record: IterationRecord, verdict: Verdict) -> None:
        """Store and emit the record, then advance or count a rejection."""
        self._stores.runs.save_iteration(run_id, record)
        self._stores.telemetry.record_iteration(run_id, record)
        loop.records.append(record)
        if verdict.accepted and verdict.standing is not None:
            loop.current = verdict.standing
            loop.rejections = 0
        else:
            loop.rejections += 1
        state = "accepted" if record.accepted else "rejected"
        _LOG.info("iteration %d %s: %s", record.iteration, state, record.reason)


def _record(
    attempt: _Attempt, baseline_version: int, candidate_version: int | None, verdict: Verdict
) -> IterationRecord:
    """Build the stored record for one attempt."""
    standing = verdict.standing
    return IterationRecord(
        iteration=attempt.number,
        proposal=attempt.proposal,
        decision=attempt.decision,
        baseline_version=baseline_version,
        candidate_version=candidate_version,
        candidate_summary=standing.eval_summary if standing is not None else None,
        guardrails=verdict.guardrails,
        accepted=verdict.accepted,
        reason=verdict.reason,
    )
