"""Choose which company data is sent to the model."""

from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from costwise.domain.company import CompanyRecord

_CHARS_PER_TOKEN = 4


class PayloadService:
    """Send the full provider payload, or only chosen normalized fields."""

    def trim(
        self,
        record: CompanyRecord,
        raw: Mapping[str, JsonValue],
        fields: Sequence[str] | None,
    ) -> dict[str, JsonValue]:
        """Return raw when fields is None, else the listed normalized fields in that order."""
        if fields is None:
            return dict(raw)
        normalized = normalized_fields(record)
        return {name: normalized[name] for name in fields}

    def estimate_tokens(self, text: str) -> int:
        """Return a rough token count (characters / 4) for logging only, never for cost."""
        return len(text) // _CHARS_PER_TOKEN


def normalized_fields(record: CompanyRecord) -> dict[str, JsonValue]:
    """Return every CompanyRecord field by name."""
    return {
        "domain": record.domain,
        "employee_count": record.employee_count,
        "funding_stage": record.funding_stage,
        "total_funding_usd": record.total_funding_usd,
        "engineering_open_roles": record.engineering_open_roles,
        "industry": record.industry,
        "headcount_growth_pct_6m": record.headcount_growth_pct_6m,
    }
