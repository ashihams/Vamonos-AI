"""In-memory fakes for unit tests."""

from tests.testing_fakes.fake_approval import ScriptedApprover
from tests.testing_fakes.fake_budget import RecordingBudget
from tests.testing_fakes.fake_clock import FixedClock, SteppingClock, TickingClock
from tests.testing_fakes.fake_data import FakeCompanySource
from tests.testing_fakes.fake_fixtures import InMemoryFixtureStore
from tests.testing_fakes.fake_llm import FakeLLMClient
from tests.testing_fakes.fake_report import RecordingDashboardSink, RecordingReportSink
from tests.testing_fakes.fake_runner import FakeRunner
from tests.testing_fakes.fake_storage import InMemoryConfigStore, InMemoryRunStore
from tests.testing_fakes.fake_telemetry import RecordingTelemetrySink

__all__ = [
    "FakeCompanySource",
    "FakeLLMClient",
    "FakeRunner",
    "FixedClock",
    "InMemoryConfigStore",
    "InMemoryFixtureStore",
    "InMemoryRunStore",
    "RecordingBudget",
    "RecordingDashboardSink",
    "RecordingReportSink",
    "RecordingTelemetrySink",
    "ScriptedApprover",
    "SteppingClock",
    "TickingClock",
]
