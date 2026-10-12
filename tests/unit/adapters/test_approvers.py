"""Tests for the automatic and terminal approvers."""

from decimal import Decimal

import pytest
import typer

from costwise.adapters.approval.auto_approver import AUTO_APPROVED_NOTE, AutoApprover
from costwise.adapters.approval.cli_approver import CliApprover, proposal_lines
from costwise.domain.config import Lever
from costwise.domain.cost import CostBreakdown
from costwise.domain.proposals import ApprovalDecision, Proposal
from tests.unit.domain.builders import make_summary

PROPOSAL = Proposal(
    lever=Lever.CACHE,
    new_value=True,
    rationale="25% of tasks repeat a domain",
    predicted_cost_change_pct=-12.5,
    risk="low",
)
EVIDENCE = make_summary(0.9, 1200).model_copy(
    update={
        "n": 32,
        "cost_per_successful_task": Decimal("0.0123"),
        "totals": CostBreakdown(
            model_usd=Decimal("0.2"), infra_usd=Decimal("0.01"), data_usd=Decimal("0.3")
        ),
    }
)


def _cli(*answers: str) -> tuple[CliApprover, list[str], list[str]]:
    """Return an approver reading answers in order, with the prompts and lines it produced."""
    pending = list(answers)
    prompts: list[str] = []
    said: list[str] = []

    def ask(prompt: str) -> str:
        """Record the prompt and return the next answer."""
        prompts.append(prompt)
        return pending.pop(0)

    return CliApprover(ask=ask, say=said.append), prompts, said


def test_auto_approver_approves_and_tags_the_note() -> None:
    """Every proposal is approved with the auto-approved note."""
    decision = AutoApprover().review(PROPOSAL, EVIDENCE)

    assert decision == ApprovalDecision(approved=True, note=AUTO_APPROVED_NOTE)


def test_cli_approver_shows_the_proposal_and_evidence() -> None:
    """Lever, value, rationale, prediction, risk, and the key numbers are printed."""
    lines = proposal_lines(PROPOSAL, EVIDENCE)

    assert lines == [
        "lever: cache_company_data",
        "new value: true",
        "rationale: 25% of tasks repeat a domain",
        "predicted cost change: -12.5%  risk: low",
        "evidence (EVAL, 32 tasks): success 90.0%, cost per successful task 0.012300 usd, "
        "p95 1200 ms",
        "cost usd: model 0.200000, infra 0.010000, data 0.300000",
    ]


def test_cli_approver_reads_yes_and_a_note() -> None:
    """A yes with a note approves and keeps the trimmed note."""
    approver, prompts, said = _cli(" Y ", "  looks safe ")

    decision = approver.review(PROPOSAL, EVIDENCE)

    assert decision == ApprovalDecision(approved=True, note="looks safe")
    assert prompts == ["apply this change? [y/n]", "note (optional)"]
    assert said == proposal_lines(PROPOSAL, EVIDENCE)


def test_cli_approver_uses_the_terminal_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without injected functions, answers come from typer.prompt and lines go to stdout."""
    answers = iter(["y", ""])
    monkeypatch.setattr(typer, "prompt", lambda *args, **kwargs: next(answers))

    decision = CliApprover().review(PROPOSAL, EVIDENCE)

    assert decision.approved
    assert "lever: cache_company_data" in capsys.readouterr().out


def test_cli_approver_asks_again_until_yes_or_no() -> None:
    """Anything but y or n is asked again; no with an empty note declines."""
    approver, prompts, said = _cli("maybe", "no", "")

    decision = approver.review(PROPOSAL, EVIDENCE)

    assert decision == ApprovalDecision(approved=False, note="")
    assert len(prompts) == 3
    assert said[-1] == "please answer y or n"
