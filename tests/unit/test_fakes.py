"""Scripted fakes used by later stages."""

from decimal import Decimal

import pytest

from costwise.domain.company import CompanyRecord
from costwise.domain.config import Lever
from costwise.domain.cost import Money
from costwise.domain.errors import CostwiseError, DataSourceError, LLMError, RunnerError
from costwise.domain.proposals import ApprovalDecision, Proposal
from costwise.domain.task import InfraCostSource, QualificationRequest, Split
from costwise.ports.data import CompanyFetch
from costwise.ports.llm import LLMRequest, LLMResponse, TokenUsage
from tests.testing_fakes import (
    FakeCompanySource,
    FakeLLMClient,
    FakeRunner,
    FixedClock,
    InMemoryConfigStore,
    InMemoryRunStore,
    RecordingTelemetrySink,
    ScriptedApprover,
)
from tests.unit.domain.builders import make_config, make_result, make_summary


def _response(text: str) -> LLMResponse:
    """Build one scripted completion."""
    return LLMResponse(
        text=text,
        usage=TokenUsage(input_tokens=3, output_tokens=4),
        latency_ms=5,
        model="cheap-model",
    )


def _request() -> LLMRequest:
    """Build one completion request."""
    return LLMRequest(model="cheap-model", system="s", user="u", max_output_tokens=64)


def test_fake_llm_replays_a_list_and_a_callable() -> None:
    """Requests are recorded and an exhausted script raises LLMError."""
    scripted = FakeLLMClient([_response("one"), _response("two")])
    assert scripted.complete(_request()).text == "one"
    assert scripted.complete(_request()).text == "two"
    assert len(scripted.requests) == 2
    with pytest.raises(LLMError, match="no scripted response"):
        scripted.complete(_request())

    called = FakeLLMClient(lambda request: _response(request.user))
    assert called.complete(_request()).text == "u"
    assert called.requests[0].user == "u"


def test_fake_company_source_records_domains() -> None:
    """A known domain is returned and an unknown domain raises."""
    record = CompanyRecord(
        domain="example.com",
        employee_count=10,
        funding_stage="seed",
        total_funding_usd=None,
        engineering_open_roles=1,
        industry=None,
        headcount_growth_pct_6m=None,
    )
    credits: Money = Decimal("2")
    fetch = CompanyFetch(record=record, raw={"domain": "example.com"}, credits_used=credits)
    source = FakeCompanySource({"example.com": fetch})
    assert source.fetch("example.com").credits_used == Decimal("2")
    with pytest.raises(DataSourceError, match="unknown domain"):
        source.fetch("missing.test")
    assert source.domains == ["example.com", "missing.test"]


def test_fake_runner_records_capabilities_and_runs() -> None:
    """Capabilities, infrastructure updates, and an exhausted script are visible."""
    from costwise.domain.task import InvocationResult

    invocation = InvocationResult(
        task_id="task-1",
        answer=None,
        calls=(),
        data_credits=Decimal(0),
        total_latency_ms=1,
        error=None,
        billed_ms=None,
        memory_mb=None,
        cold_start=False,
    )
    request = QualificationRequest(
        task_id="task-1",
        domain="example.com",
        split=Split.EVAL,
        data_cache_hit=False,
    )
    runner = FakeRunner(frozenset({Lever.CACHE}), InfraCostSource.MODELED, [invocation])
    assert runner.capabilities().infra_source is InfraCostSource.MODELED
    runner.apply_infra(make_config())
    assert runner.run(request, make_config()) == invocation
    assert len(runner.applied) == 1
    assert len(runner.runs) == 1
    with pytest.raises(RunnerError, match="no scripted invocation"):
        runner.run(request, make_config())


def test_telemetry_clock_approver_and_memory_stores() -> None:
    """The remaining fakes record calls and raise when a script or key is missing."""
    sink = RecordingTelemetrySink()
    result = make_result()
    summary = make_summary(1.0, 10)
    sink.record_task("run-1", result)
    sink.record_summary("run-1", 1, summary)
    sink.flush()
    assert sink.tasks == [("run-1", result)]
    assert sink.summaries[0][1] == 1
    assert sink.flushed is True
    assert FixedClock(7).now_ns() == 7

    proposal = Proposal(
        lever=Lever.CACHE,
        new_value=True,
        rationale="cache",
        predicted_cost_change_pct=-1.0,
        risk="low",
    )
    decision = ApprovalDecision(approved=True, note="ok")
    approver = ScriptedApprover([decision])
    assert approver.review(proposal, summary) == decision
    with pytest.raises(CostwiseError, match="no scripted decision"):
        approver.review(proposal, summary)

    runs = InMemoryRunStore()
    configs = InMemoryConfigStore()
    runs.save_results("run-1", 1, [result])
    assert runs.load_results("run-1", 1) == [result]
    assert runs.load_iterations("missing") == []
    config = make_config()
    configs.save("run-1", config)
    assert configs.load("run-1", 1) == config
    with pytest.raises(CostwiseError, match="missing store file: results"):
        runs.load_results("missing", 1)
    with pytest.raises(CostwiseError, match="missing store file: config"):
        configs.load("missing", 1)
