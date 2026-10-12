"""A fixed run, a baseline and three iterations, for report tests."""

from decimal import Decimal

from costwise.domain.config import Lever
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from costwise.domain.task import InfraCostSource, Split, TaskResult
from costwise.services.report import ReportService
from tests.testing_fakes import InMemoryRunStore, RecordingReportSink
from tests.unit.domain.builders import ResultSpec, make_result

RUN_ID = "golden-run"


def version_results(
    version: int, model_usd: str, outcomes: tuple[bool, bool, bool, bool]
) -> list[TaskResult]:
    """Return three evaluation tasks and one held-out task with the given outcomes."""
    splits = (Split.EVAL, Split.EVAL, Split.EVAL, Split.HELDOUT)
    return [
        make_result(
            ResultSpec(
                task_id=f"task-{index:04d}",
                split=split,
                success=success,
                model_usd=Decimal(model_usd),
                infra_usd=Decimal("0.0005"),
                data_usd=Decimal("0.004"),
                total_latency_ms=100 * (index + 1),
                config_version=version,
                infra_source=InfraCostSource.MODELED,
            )
        )
        for index, (split, success) in enumerate(zip(splits, outcomes, strict=True))
    ]


def record(
    iteration: int,
    lever: Lever,
    new_value: bool | int | dict[str, int],
    decision: ApprovalDecision,
    outcome: tuple[int | None, bool, str],
) -> IterationRecord:
    """Return one iteration record; outcome is candidate version, accepted, and reason."""
    candidate_version, accepted, reason = outcome
    proposal = Proposal(
        lever=lever,
        new_value=new_value,
        rationale="test",
        predicted_cost_change_pct=-10.0,
        risk="low",
    )
    return IterationRecord(
        iteration=iteration,
        proposal=proposal,
        decision=decision,
        baseline_version=1,
        candidate_version=candidate_version,
        candidate_summary=None,
        guardrails=None,
        accepted=accepted,
        reason=reason,
    )


def scenario_store() -> InMemoryRunStore:
    """Return a run whose v2 is kept, v3 is rolled back, and third proposal is declined."""
    runs = InMemoryRunStore()
    runs.save_results(RUN_ID, 1, version_results(1, "0.01", (True, True, False, True)))
    runs.save_results(RUN_ID, 2, version_results(2, "0.006", (True, True, False, True)))
    runs.save_results(RUN_ID, 3, version_results(3, "0.003", (True, False, False, False)))
    approved = ApprovalDecision(approved=True, note="auto-approved")
    runs.save_iteration(
        RUN_ID, record(1, Lever.CACHE, True, approved, (2, True, "guardrails passed"))
    )
    routing = {"strong_if_missing_fields_gte": 2}
    risky = ApprovalDecision(approved=True, note="try it | watch held-out")
    failed = (3, False, "guardrails failed: eval_success, heldout_success")
    runs.save_iteration(RUN_ID, record(2, Lever.ROUTING, routing, risky, failed))
    declined = ApprovalDecision(approved=False, note="")
    runs.save_iteration(
        RUN_ID,
        record(3, Lever.MAX_OUTPUT_TOKENS, 256, declined, (None, False, "rejected by approver")),
    )
    return runs


def scenario_service() -> tuple[ReportService, RecordingReportSink]:
    """Return a report service over the scenario and the sink it writes to."""
    sink = RecordingReportSink()
    return ReportService(scenario_store(), sink), sink
