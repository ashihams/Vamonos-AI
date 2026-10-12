"""Helper scripts that wrap the CLI."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from costwise.domain.config import Lever
from costwise.domain.proposals import ApprovalDecision
from tests.testing_fakes import InMemoryRunStore, RecordingTelemetrySink
from tests.unit.domain.builders import ResultSpec, make_result
from tests.unit.services.report_support import record

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str) -> ModuleType:
    """Import a script file as a module without running its main block."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_run_script_asks_for_five_tasks_and_passes_extra_arguments() -> None:
    """The wrapper runs the five-task budget check and forwards any other options."""
    script = _load("dry_run")
    assert script.dry_run_args([]) == ["dry-run", "--tasks", "5"]
    assert script.dry_run_args(["--runner", "lambda"])[-2:] == ["--runner", "lambda"]


def test_dry_run_script_runs_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """main hands the arguments to the costwise app; --help exits cleanly."""
    script = _load("dry_run")
    monkeypatch.setattr("sys.argv", ["dry_run.py", "--help"])
    with pytest.raises(SystemExit) as exited:
        script.main()
    assert exited.value.code == 0


def test_replay_sends_every_stored_version_then_the_iterations() -> None:
    """All results of v1 and v2 go out in order, followed by the iteration record."""
    script = _load("replay_neatlogs")
    runs, sink = InMemoryRunStore(), RecordingTelemetrySink()
    runs.save_results("demo", 1, [make_result(ResultSpec(task_id="a"))])
    runs.save_results("demo", 2, [make_result(ResultSpec(task_id="b", config_version=2))])
    approved = ApprovalDecision(approved=True, note="")
    runs.save_iteration("demo", record(1, Lever.CACHE, True, approved, (2, False, "no saving")))

    assert script.replay("demo", runs, sink) == (2, 1)
    assert [result.request.task_id for _, result in sink.tasks] == ["a", "b"]
    assert [run_id for run_id, _ in sink.iterations] == ["demo"]


def test_replay_of_an_unknown_run_sends_nothing() -> None:
    """A run with no stored results replays zero tasks and zero iterations."""
    script = _load("replay_neatlogs")
    sink = RecordingTelemetrySink()
    assert script.replay("missing", InMemoryRunStore(), sink) == (0, 0)
    assert sink.tasks == []
