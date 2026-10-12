"""LocalRunner, SystemClock, and NullSink."""

from costwise.adapters.runners.local_runner import LocalRunner
from costwise.adapters.system_clock import SystemClock
from costwise.adapters.telemetry.null_sink import NullSink
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.task import InfraCostSource, InvocationResult, QualificationRequest
from tests.testing_fakes import TickingClock
from tests.unit.domain.builders import make_config, make_result, make_summary
from tests.unit.eval_support import make_invocation, make_requests


class _Task:
    """Qualification task that returns a fixed invocation."""

    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult:
        """Return a correct answer with no runner fields."""
        del config
        return make_invocation(request, True)


def test_capabilities_exclude_memory_and_infra_is_modeled() -> None:
    """Locally, every lever but Lambda memory is available and infra cost is modeled."""
    capabilities = LocalRunner(_Task(), TickingClock([])).capabilities()
    assert Lever.LAMBDA_MEMORY not in capabilities.levers
    assert capabilities.levers == {
        Lever.ROUTING,
        Lever.PAYLOAD_FIELDS,
        Lever.MAX_OUTPUT_TOKENS,
        Lever.CACHE,
    }
    assert capabilities.infra_source is InfraCostSource.MODELED


def test_run_bills_wall_time_rounded_up_at_configured_memory() -> None:
    """1.2 ms of wall time bills 2 ms; memory comes from the config; apply_infra changes nothing."""
    runner = LocalRunner(_Task(), TickingClock([10_000_000, 11_200_000]))
    config = make_config()
    runner.apply_infra(config)
    invocation = runner.run(make_requests(0)[0], config)
    assert invocation.billed_ms == 2
    assert invocation.memory_mb == config.lambda_memory_mb
    assert invocation.answer is not None


def test_system_clock_and_null_sink() -> None:
    """The system clock moves forward; the null sink accepts every call."""
    clock = SystemClock()
    first = clock.now_ns()
    assert clock.now_ns() >= first > 0
    sink = NullSink()
    sink.record_task("run-1", make_result())
    sink.record_summary("run-1", 1, make_summary(1.0, 10))
    sink.flush()
