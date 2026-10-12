"""Map one Crustdata company_data object to a CompanyRecord."""

from collections.abc import Mapping

from costwise.domain.company import CompanyRecord
from costwise.domain.errors import DataSourceError
from costwise.domain.proposals import JsonValue

JsonObject = Mapping[str, JsonValue]


def map_company(raw: JsonObject) -> CompanyRecord:
    """Return the normalized company. Missing or mistyped fields become None.

    ``engineering_open_roles`` is ``hiring.openings_count``, which counts all
    open roles, because the enrich response has no engineering-only count.
    """
    basic = _section(raw, "basic_info")
    headcount = _section(raw, "headcount")
    funding = _section(raw, "funding")
    hiring = _section(raw, "hiring")
    taxonomy = _section(raw, "taxonomy")
    domain = _text(basic.get("primary_domain"))
    if domain is None:
        raise DataSourceError("company has no primary domain")
    return CompanyRecord(
        domain=domain,
        employee_count=_whole(headcount.get("total")),
        funding_stage=_text(funding.get("last_round_type")),
        total_funding_usd=_whole(funding.get("total_investment_usd")),
        engineering_open_roles=_whole(hiring.get("openings_count")),
        industry=_text(taxonomy.get("professional_network_industry")),
        headcount_growth_pct_6m=_number(_section(headcount, "growth_percent").get("six_months")),
    )


def _section(raw: JsonObject, key: str) -> JsonObject:
    """Return a nested object, or an empty one when it is absent or not an object."""
    value = raw.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _text(value: JsonValue) -> str | None:
    """Return a non-empty string or None."""
    if isinstance(value, str) and value:
        return value
    return None


def _number(value: JsonValue) -> float | None:
    """Return an int or float as float, rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _whole(value: JsonValue) -> int | None:
    """Return a whole number, accepting floats such as 141000000.0."""
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)
