"""Parse the REPORT line Lambda appends to every invocation log."""

import re

from costwise.domain.errors import RunnerError
from costwise.domain.frozen import FrozenModel

_REPORT = re.compile(
    r"REPORT RequestId: \S+\s+"
    r"Duration: (?P<duration>\d+(?:\.\d+)?) ms\s+"
    r"Billed Duration: (?P<billed>\d+) ms\s+"
    r"Memory Size: (?P<memory>\d+) MB\s+"
    r"Max Memory Used: (?P<used>\d+) MB"
    r"(?:\s+Init Duration: (?P<init>\d+(?:\.\d+)?) ms)?"
)


class LambdaReport(FrozenModel):
    """Measured duration, billing, and memory for one invocation."""

    duration_ms: float
    billed_ms: int
    memory_mb: int
    max_memory_used_mb: int
    init_duration_ms: float | None

    @property
    def cold_start(self) -> bool:
        """Return whether the invocation paid an init phase."""
        return self.init_duration_ms is not None


def parse_report_line(log: str) -> LambdaReport:
    """Return the last REPORT line in log, or raise RunnerError when there is none."""
    matches = list(_REPORT.finditer(log))
    if not matches:
        raise RunnerError("no REPORT line in the Lambda log")
    found = matches[-1]
    init = found.group("init")
    return LambdaReport(
        duration_ms=float(found.group("duration")),
        billed_ms=int(found.group("billed")),
        memory_mb=int(found.group("memory")),
        max_memory_used_mb=int(found.group("used")),
        init_duration_ms=float(init) if init is not None else None,
    )
