"""File report sink: where files land and which names it refuses."""

from pathlib import Path

import pytest

from costwise.adapters.storage.dashboard_file import FileDashboardSink
from costwise.adapters.storage.report_files import FileReportSink
from costwise.domain.errors import CostwiseError


def test_writes_files_into_the_run_report_folder(tmp_path: Path) -> None:
    """Files go under <root>/<run_id>/report with LF newlines, replacing old copies."""
    sink = FileReportSink(tmp_path)
    sink.write("run-1", {"report.md": "old\n"})
    location = sink.write("run-1", {"report.md": "# title\nbody\n", "trajectory.csv": "a,b\n"})
    folder = tmp_path / "run-1" / "report"
    assert location == folder.as_posix()
    assert (folder / "report.md").read_bytes() == b"# title\nbody\n"
    assert (folder / "trajectory.csv").read_bytes() == b"a,b\n"


@pytest.mark.parametrize("name", ["../escape.md", "Report.md", "no_extension", "sub/report.md"])
def test_rejects_unsafe_file_names(tmp_path: Path, name: str) -> None:
    """Names with paths, capitals, or no extension are refused before anything is written."""
    with pytest.raises(CostwiseError, match="invalid report file names"):
        FileReportSink(tmp_path).write("run-1", {name: "x", "report.md": "y"})
    assert not (tmp_path / "run-1").exists()


def test_dashboard_sink_creates_the_folder_and_replaces_the_file(tmp_path: Path) -> None:
    """The document lands at the given path with LF newlines; a second write replaces it."""
    path = tmp_path / "public" / "data" / "dashboard.json"
    sink = FileDashboardSink(path)
    sink.write('{"runs": [1]}\n')
    assert sink.write('{"runs": []}\n') == path.as_posix()
    assert path.read_bytes() == b'{"runs": []}\n'


def test_rejects_unsafe_run_ids(tmp_path: Path) -> None:
    """The run id is checked like every other store does."""
    with pytest.raises(CostwiseError):
        FileReportSink(tmp_path).write("../outside", {"report.md": "x"})
