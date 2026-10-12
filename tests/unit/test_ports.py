"""Import every port so the package surface stays wired."""

from costwise.domain.config import Lever
from costwise.domain.task import InfraCostSource
from costwise.ports.approval import Approver
from costwise.ports.clock import Clock
from costwise.ports.data import CompanyDataSource
from costwise.ports.llm import LLMClient
from costwise.ports.runner import RunnerCapabilities, TaskRunner
from costwise.ports.storage import ConfigStore, RunStore
from costwise.ports.telemetry import TelemetrySink


def test_port_modules_expose_their_protocols() -> None:
    """Each port module defines the protocol later stages implement."""
    protocols = (
        LLMClient,
        CompanyDataSource,
        TaskRunner,
        TelemetrySink,
        RunStore,
        ConfigStore,
        Approver,
        Clock,
    )
    assert [item.__name__ for item in protocols] == [
        "LLMClient",
        "CompanyDataSource",
        "TaskRunner",
        "TelemetrySink",
        "RunStore",
        "ConfigStore",
        "Approver",
        "Clock",
    ]
    capabilities = RunnerCapabilities(
        levers=frozenset({Lever.ROUTING}),
        infra_source=InfraCostSource.MODELED,
    )
    assert capabilities.infra_source is InfraCostSource.MODELED
