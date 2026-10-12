"""The human-readable report and the full set of report files."""

import json
from collections.abc import Sequence
from decimal import Decimal

from costwise.domain.proposals import IterationRecord
from costwise.services.report_data import ReportData
from costwise.services.report_exports import render_cfo_inputs, render_csv, render_mermaid
from costwise.services.report_format import (
    DATA_SOURCE,
    MODEL_SOURCE,
    TOTAL_SOURCE,
    change_pct,
    infra_source,
    percent,
    signed_pct,
    source_notes,
    usd,
)

REPORT_FILE = "report.md"
CSV_FILE = "trajectory.csv"
CFO_FILE = "cfo_inputs.json"
MERMAID_FILE = "trajectory.mmd"


def _cell(text: str) -> str:
    """Make text safe inside one Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _cost_row(label: str, source: str, before: Decimal | None, after: Decimal | None) -> str:
    """Return one cost row with its source tag and change."""
    change = signed_pct(change_pct(before, after))
    return f"| {label} [source: {source}] | {usd(before)} | {usd(after)} | {change} |"


def _ms(value: int | None) -> str:
    """Format milliseconds, or n/a."""
    return "n/a" if value is None else str(value)


def _decision(record: IterationRecord) -> str:
    """Return the approval decision with its note."""
    verb = "approved" if record.decision.approved else "declined"
    return f"{verb} ({_cell(record.decision.note)})" if record.decision.note else verb


def _iteration_lines(records: Sequence[IterationRecord]) -> list[str]:
    """Return the iteration table, or a sentence when there were none."""
    if not records:
        return ["No iterations ran."]
    rows = [
        f"| {r.iteration} | {r.proposal.lever.value} | {_cell(json.dumps(r.proposal.new_value))} "
        f"| {_decision(r)} | {'yes' if r.accepted else 'no'} | {_cell(r.reason)} |"
        for r in records
    ]
    return [
        "| # | Lever | New value | Decision | Kept | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
    ]


def render_markdown(data: ReportData) -> str:
    """Return report.md: costs with sources, quality, iterations, and provenance."""
    base, final = data.baseline, data.final
    lines = [
        f"# costwise report: {data.run_id}",
        "",
        f"Baseline is config v{base.version}; the final accepted config is v{final.version}. "
        f"The baseline ran {base.tasks} tasks ({base.eval_tasks} evaluation, "
        f"{base.heldout_tasks} held-out). Costs and p95 latency cover every task in a "
        "version; success rates are per split.",
        "",
        "## Cost",
        "",
        f"| Metric | Baseline v{base.version} | Final v{final.version} | Change |",
        "| --- | --- | --- | --- |",
        _cost_row(
            "Cost per successful task, USD",
            TOTAL_SOURCE,
            base.cost_per_successful_task,
            final.cost_per_successful_task,
        ),
        _cost_row("Model cost, USD", MODEL_SOURCE, base.totals.model_usd, final.totals.model_usd),
        _cost_row(
            "Infra cost, USD",
            infra_source(base, final),
            base.totals.infra_usd,
            final.totals.infra_usd,
        ),
        _cost_row("Data cost, USD", DATA_SOURCE, base.totals.data_usd, final.totals.data_usd),
        _cost_row("Total cost, USD", TOTAL_SOURCE, base.totals.total_usd, final.totals.total_usd),
        "",
        "## Quality and latency",
        "",
        f"| Metric | Baseline v{base.version} | Final v{final.version} |",
        "| --- | --- | --- |",
        f"| Success rate, evaluation split | {percent(base.eval_success_rate)} "
        f"| {percent(final.eval_success_rate)} |",
        f"| Success rate, held-out split (never shown to the optimizer) "
        f"| {percent(base.heldout_success_rate)} | {percent(final.heldout_success_rate)} |",
        f"| p95 latency, ms (cold starts excluded) | {_ms(base.p95_latency_ms)} "
        f"| {_ms(final.p95_latency_ms)} |",
        "",
        "## Iterations",
        "",
        *_iteration_lines(data.iterations),
        "",
        "Every evaluated version, including rolled-back ones, is in `trajectory.csv`; "
        "`trajectory.mmd` charts cost per successful task across them.",
        "",
        "## What is measured and what is modeled",
        "",
        *source_notes(base, final),
    ]
    return "\n".join(lines) + "\n"


def render_files(data: ReportData) -> dict[str, str]:
    """Return every report file by name."""
    return {
        REPORT_FILE: render_markdown(data),
        CSV_FILE: render_csv(data),
        CFO_FILE: render_cfo_inputs(data),
        MERMAID_FILE: render_mermaid(data),
    }
