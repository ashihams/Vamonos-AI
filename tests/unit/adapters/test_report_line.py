"""Tests for parsing the Lambda REPORT log line."""

import pytest

from costwise.adapters.runners.report_line import LambdaReport, parse_report_line
from costwise.domain.errors import RunnerError

WARM = (
    "START RequestId: 1f2e Version: $LATEST\n"
    "END RequestId: 1f2e\n"
    "REPORT RequestId: 1f2e\tDuration: 123.45 ms\tBilled Duration: 124 ms\t"
    "Memory Size: 512 MB\tMax Memory Used: 100 MB\t\n"
)
COLD = (
    "REPORT RequestId: 9a8b Duration: 2034.10 ms Billed Duration: 2035 ms "
    "Memory Size: 1024 MB Max Memory Used: 180 MB Init Duration: 812.33 ms"
)


def test_parses_a_warm_report() -> None:
    """A tab-separated line without Init Duration is a warm start."""
    report = parse_report_line(WARM)

    assert report == LambdaReport(
        duration_ms=123.45,
        billed_ms=124,
        memory_mb=512,
        max_memory_used_mb=100,
        init_duration_ms=None,
    )
    assert not report.cold_start


def test_parses_a_cold_report() -> None:
    """Init Duration marks a cold start."""
    report = parse_report_line(COLD)

    assert report.billed_ms == 2035
    assert report.memory_mb == 1024
    assert report.init_duration_ms == pytest.approx(812.33)
    assert report.cold_start


def test_uses_the_last_report_in_the_log() -> None:
    """When the tail holds two invocations, the latest one counts."""
    assert parse_report_line(COLD + "\n" + WARM).billed_ms == 124


@pytest.mark.parametrize(
    "log",
    [
        "",
        "END RequestId: 1f2e\n",
        "REPORT RequestId: 1f2e Duration: fast Billed Duration: 124 ms",
    ],
)
def test_rejects_a_log_without_a_report_line(log: str) -> None:
    """A missing or malformed REPORT line is a runner error."""
    with pytest.raises(RunnerError, match="no REPORT line"):
        parse_report_line(log)
