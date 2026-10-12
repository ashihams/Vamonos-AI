"""Collect per-version evidence from the stores and publish the report files."""

from costwise.domain.frozen import FrozenModel
from costwise.ports.report import ReportSink
from costwise.ports.storage import RunStore
from costwise.services.report_data import (
    BASELINE,
    KEPT,
    ROLLED_BACK,
    ReportData,
    version_stats,
)
from costwise.services.report_render import render_files

BASELINE_VERSION = 1


class ReportBundle(FrozenModel):
    """Where the report went and the numbers it shows."""

    location: str
    data: ReportData


class ReportService:
    """Read stored results and iterations, then render and store the evidence pack."""

    def __init__(self, runs: RunStore, sink: ReportSink) -> None:
        """Read from runs and write through sink."""
        self._runs = runs
        self._sink = sink

    def collect(self, run_id: str) -> ReportData:
        """Return stats for the baseline and every candidate version that ran."""
        return collect_report(self._runs, run_id)

    def build(self, run_id: str) -> ReportBundle:
        """Render the report files, store them, and return where they went."""
        data = self.collect(run_id)
        return ReportBundle(location=self._sink.write(run_id, render_files(data)), data=data)


def collect_report(runs: RunStore, run_id: str) -> ReportData:
    """Return stats for the baseline and every candidate version that ran."""
    iterations = tuple(runs.load_iterations(run_id))
    baseline = version_stats(
        BASELINE_VERSION, BASELINE, runs.load_results(run_id, BASELINE_VERSION)
    )
    versions = [baseline]
    final = baseline
    for record in iterations:
        if record.candidate_version is None:
            continue
        status = KEPT if record.accepted else ROLLED_BACK
        results = runs.load_results(run_id, record.candidate_version)
        stats = version_stats(record.candidate_version, status, results)
        versions.append(stats)
        if record.accepted:
            final = stats
    return ReportData(
        run_id=run_id,
        baseline=baseline,
        final=final,
        versions=tuple(versions),
        iterations=iterations,
    )
