"""EvaluationService: order, cache hits, budget stop, scoring, and sinks."""

import logging
import threading
from decimal import Decimal

import pytest

from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import ConfigError, RunnerError
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest
from costwise.services.evaluation import with_cache_hits
from tests.testing_fakes import FakeRunner
from tests.testing_fakes.fake_budget import RecordingBudget
from tests.unit.domain.builders import make_config
from tests.unit.eval_support import (
    LOCAL_LEVERS,
    answering_runner,
    domain,
    make_evaluation,
    make_invocation,
    make_labels,
    make_requests,
)


def test_results_follow_request_order_even_when_later_tasks_finish_first() -> None:
    """The first task waits for the second to start, yet results keep request order."""
    labels = make_labels(2)
    second_started = threading.Event()

    def respond(request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Hold task one until task two has run."""
        del config
        if request.task_id == "task-0001":
            assert second_started.wait(timeout=5)
        else:
            second_started.set()
        return make_invocation(request, labels[request.domain].expected_fit)

    runner = FakeRunner(LOCAL_LEVERS, InfraCostSource.MODELED, respond)
    harness = make_evaluation(runner, labels)
    results = harness.service.evaluate("run-1", make_config(), make_requests(0, 1), max_workers=2)
    assert [r.request.task_id for r in results] == ["task-0001", "task-0002"]


def test_results_are_scored_costed_and_sent_to_every_sink() -> None:
    """Success uses the label; costs use the price book; telemetry gets one record per result."""
    labels = make_labels(3)
    harness = make_evaluation(answering_runner(labels, wrong={domain(1)}), labels)
    config = make_config()
    results = harness.service.evaluate("run-1", config, make_requests(0, 1, 2))
    assert [r.success for r in results] == [True, False, True]
    assert [r.difficulty.value for r in results] == ["easy", "hard", "easy"]
    first = results[0]
    assert first.costs.model_usd == Decimal("0.0034")
    assert first.costs.data_usd == Decimal("0.02")
    assert first.infra_source is InfraCostSource.MODELED
    assert first.config_version == config.version
    assert first.started_at_ns == 1_000
    assert [task for _, task in harness.telemetry.tasks] == results
    assert harness.store.load_results("run-1", config.version) == results


def test_cache_hits_are_decided_by_first_occurrence_only_when_cache_is_on() -> None:
    """Repeats of an earlier domain are hits with the cache on and misses with it off."""
    requests = make_requests(0, 1, 0, 2, 1)
    assert [r.data_cache_hit for r in with_cache_hits(requests, True)] == [
        False,
        False,
        True,
        False,
        True,
    ]
    assert not any(r.data_cache_hit for r in with_cache_hits(requests, False))

    labels = make_labels(3)
    runner = answering_runner(labels)
    harness = make_evaluation(runner, labels)
    cached = make_config().model_copy(update={"cache_company_data": True})
    results = harness.service.evaluate("run-1", cached, requests)
    assert [r.costs.data_usd for r in results] == [Decimal("0.02")] * 2 + [Decimal(0)] + [
        Decimal("0.02"),
        Decimal(0),
    ]
    assert [request.data_cache_hit for request, _ in runner.runs] == [
        False,
        False,
        True,
        False,
        True,
    ]


def test_budget_stop_returns_partial_results_and_logs_a_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After three allowed checks no more tasks are submitted; finished ones are kept."""
    monkeypatch.setattr(logging.getLogger("costwise"), "propagate", True)
    labels = make_labels(5)
    budget = RecordingBudget(allowed_checks=3)
    harness = make_evaluation(answering_runner(labels), labels, budget)
    with caplog.at_level(logging.WARNING, logger="costwise.services.evaluation"):
        results = harness.service.evaluate(
            "run-1", make_config(), make_requests(0, 1, 2, 3, 4), max_workers=2
        )
    assert [r.request.task_id for r in results] == ["task-0001", "task-0002", "task-0003"]
    assert "budget stop after 3 of 5 tasks" in caplog.text
    assert len(harness.telemetry.tasks) == 3
    assert len(harness.store.load_results("run-1", 1)) == 3


def test_runner_failure_becomes_an_errored_task(caplog: pytest.LogCaptureFixture) -> None:
    """One failed invocation is scored as an error with no cost; the run continues."""
    labels = make_labels(2)

    def respond(request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Fail the first task only."""
        del config
        if request.task_id == "task-0001":
            raise RunnerError("lambda function error: Unhandled")
        return make_invocation(request, labels[request.domain].expected_fit)

    harness = make_evaluation(FakeRunner(LOCAL_LEVERS, InfraCostSource.MODELED, respond), labels)
    with caplog.at_level(logging.WARNING):
        failed, passed = harness.service.evaluate("run-1", make_config(), make_requests(0, 1))

    assert failed.invocation.error == "RunnerError: lambda function error: Unhandled"
    assert not failed.success
    assert failed.costs.total_usd == Decimal(0)
    assert passed.success
    assert "runner failed for task-0001" in caplog.text


def test_unlabeled_domains_and_bad_worker_counts_are_config_errors() -> None:
    """Requests must all be labeled, and at least one worker is needed."""
    labels = make_labels(1)
    harness = make_evaluation(answering_runner(labels), labels)
    with pytest.raises(ConfigError, match="no label for: c05"):
        harness.service.evaluate("run-1", make_config(), make_requests(0, 5))
    with pytest.raises(ConfigError, match="max_workers"):
        harness.service.evaluate("run-1", make_config(), make_requests(0), max_workers=0)
