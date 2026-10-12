"""Source tags, plain-language provenance notes, and number formats for the report."""

from decimal import Decimal

from costwise.domain.task import InfraCostSource
from costwise.services.report_data import VersionStats

MODEL_SOURCE = "measured tokens x configured prices"
DATA_SOURCE = "modeled from fixture credits x configured price"
TOTAL_SOURCE = "model + infra + data"
INFRA_MEASURED = "measured from Lambda REPORT lines"
INFRA_MODELED = "modeled from local wall time"

_MODEL_NOTE = (
    "- Model cost is measured: each call's input and output token counts as reported by "
    "the model endpoint, times the per-token prices in `config/pricing.yaml`. The prices "
    "are configuration, not a bill."
)
_INFRA_NOTES = {
    INFRA_MEASURED: (
        "- Infra cost is measured: billed duration and memory size from each Lambda "
        "invocation's REPORT line, times the Lambda prices in `config/pricing.yaml`. "
        "Cold starts are left out of p95 latency."
    ),
    INFRA_MODELED: (
        "- Infra cost is modeled: tasks ran on this machine, so the Lambda price formula is "
        "applied to local wall time and the configured memory. It is not a bill, and the "
        "memory lever was not available."
    ),
}
_MIXED_INFRA_NOTE = (
    "- Infra cost mixes measured and modeled versions, so compare infra numbers with care."
)
_DATA_NOTE = (
    "- Data cost is modeled: the Crustdata credits recorded when each company fixture was "
    "fetched, times the per-credit price in `config/pricing.yaml`. Companies come from "
    "frozen fixtures; a repeated company is a cache hit only when the cache lever is on."
)
_HELDOUT_NOTE = (
    "- Held-out companies are never shown to the optimizer or the approver. Their success "
    "rate is reported separately and is one of the guardrails."
)
_LABEL_NOTE = (
    "- Success means the model's fit answer matches a label from the rule-based ICP check, "
    "not a human judgment."
)


def infra_source(*stats: VersionStats) -> str:
    """Return how the infra cost of these versions was obtained."""
    sources = {source for stat in stats for source in stat.infra_sources}
    if sources == {InfraCostSource.MEASURED}:
        return INFRA_MEASURED
    if sources == {InfraCostSource.MODELED}:
        return INFRA_MODELED
    if not sources:
        return "no tasks ran"
    return "mixed: " + " and ".join(sorted(source.value for source in sources))


def source_notes(*stats: VersionStats) -> list[str]:
    """Return the measured-versus-modeled explanation as Markdown bullets."""
    infra = _INFRA_NOTES.get(infra_source(*stats), _MIXED_INFRA_NOTE)
    return [_MODEL_NOTE, infra, _DATA_NOTE, _HELDOUT_NOTE, _LABEL_NOTE]


def change_pct(before: Decimal | None, after: Decimal | None) -> Decimal | None:
    """Return the percentage change rounded to 0.1, or None when it is undefined."""
    if before is None or after is None or before == 0:
        return None
    return round((after - before) / before * 100, 1)


def usd(value: Decimal | None) -> str:
    """Format money with six decimals, or n/a."""
    return "n/a" if value is None else f"{value:.6f}"


def percent(rate: float | None) -> str:
    """Format a 0-1 rate as a percentage, or n/a."""
    return "n/a" if rate is None else f"{rate:.1%}"


def signed_pct(change: Decimal | None) -> str:
    """Format a percentage change with its sign, or n/a."""
    return "n/a" if change is None else f"{change:+.1f}%"
