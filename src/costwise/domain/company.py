"""Normalized company record used by the qualification rule."""

from costwise.domain.frozen import FrozenModel


class CompanyRecord(FrozenModel):
    """Company facts the ICP rule can read. Missing facts are None."""

    domain: str
    employee_count: int | None
    funding_stage: str | None
    total_funding_usd: int | None
    engineering_open_roles: int | None
    industry: str | None
    headcount_growth_pct_6m: float | None


COMPANY_FIELD_NAMES: frozenset[str] = frozenset(CompanyRecord.model_fields)
