"""Machine-readable report files: the trajectory CSV, cfo.ai inputs, and a Mermaid chart."""

import csv
import io
import json
from decimal import Decimal

from costwise.services.report_data import ReportData, VersionStats
from costwise.services.report_format import (
    DATA_SOURCE,
    MODEL_SOURCE,
    change_pct,
    infra_source,
    usd,
)

CSV_COLUMNS = (
    "version",
    "status",
    "tasks",
    "successes",
    "cost_per_successful_task_usd",
    "model_usd",
    "infra_usd",
    "data_usd",
    "eval_success_rate",
    "heldout_success_rate",
    "p95_latency_ms",
    "infra_source",
)
ASSUMPTIONS_NOTE = "Fill these in for the cfo.ai model. They are assumptions, not measurements."


def _rate(rate: float | None) -> str:
    """Format a rate with four decimals, or leave it empty."""
    return "" if rate is None else f"{rate:.4f}"


def render_csv(data: ReportData) -> str:
    """Return one row per evaluated version."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for stats in data.versions:
        writer.writerow(
            (
                stats.version,
                stats.status,
                stats.tasks,
                stats.successes,
                ""
                if stats.cost_per_successful_task is None
                else usd(stats.cost_per_successful_task),
                usd(stats.totals.model_usd),
                usd(stats.totals.infra_usd),
                usd(stats.totals.data_usd),
                _rate(stats.eval_success_rate),
                _rate(stats.heldout_success_rate),
                "" if stats.p95_latency_ms is None else stats.p95_latency_ms,
                infra_source(stats),
            )
        )
    return buffer.getvalue()


def _money(value: Decimal | None) -> str | None:
    """Return money as a six-decimal string, or None."""
    return None if value is None else usd(value)


def _cfo_version(stats: VersionStats) -> dict[str, object]:
    """Return one version's numbers for cfo.ai."""
    return {
        "version": stats.version,
        "tasks": stats.tasks,
        "successes": stats.successes,
        "cost_per_successful_task_usd": _money(stats.cost_per_successful_task),
        "model_usd": usd(stats.totals.model_usd),
        "infra_usd": usd(stats.totals.infra_usd),
        "data_usd": usd(stats.totals.data_usd),
        "success_rate_eval": _rounded(stats.eval_success_rate),
        "success_rate_heldout": _rounded(stats.heldout_success_rate),
    }


def _rounded(rate: float | None) -> float | None:
    """Round a rate to four decimals, keeping None."""
    return None if rate is None else round(rate, 4)


def render_cfo_inputs(data: ReportData) -> str:
    """Return the baseline and optimized unit costs, sources, and blank assumptions."""
    change = change_pct(data.baseline.cost_per_successful_task, data.final.cost_per_successful_task)
    body: dict[str, object] = {
        "run_id": data.run_id,
        "baseline": _cfo_version(data.baseline),
        "optimized": _cfo_version(data.final),
        "cost_per_successful_task_change_pct": None if change is None else float(change),
        "sources": {
            "model_usd": MODEL_SOURCE,
            "infra_usd": infra_source(data.baseline, data.final),
            "data_usd": DATA_SOURCE,
        },
        "assumptions": {
            "note": ASSUMPTIONS_NOTE,
            "price_per_task_usd": None,
            "monthly_volume_scenarios": [],
        },
    }
    return json.dumps(body, indent=2) + "\n"


def render_mermaid(data: ReportData) -> str:
    """Return a Mermaid xychart of cost per successful task across versions."""
    priced = [s for s in data.versions if s.cost_per_successful_task is not None]
    labels = ", ".join(f'"v{s.version} {s.status}"' for s in priced)
    values = ", ".join(usd(s.cost_per_successful_task) for s in priced)
    return (
        "xychart-beta\n"
        '    title "Cost per successful task by config version"\n'
        f"    x-axis [{labels}]\n"
        '    y-axis "USD per successful task"\n'
        f"    line [{values}]\n"
    )
