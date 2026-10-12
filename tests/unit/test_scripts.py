"""Helper scripts that wrap the CLI."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

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
