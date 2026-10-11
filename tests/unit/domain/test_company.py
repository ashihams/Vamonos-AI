"""Company record constraints."""

import pytest
from pydantic import ValidationError

from costwise.domain.company import COMPANY_FIELD_NAMES, CompanyRecord
from tests.unit.domain.builders import make_company


def test_company_record_is_frozen() -> None:
    """Company records reject mutation and unknown fields."""
    record = make_company(200, "series_a", 20)
    with pytest.raises(ValidationError):
        record.domain = "other.com"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        CompanyRecord.model_validate(
            {
                "domain": "example.com",
                "employee_count": 1,
                "funding_stage": None,
                "total_funding_usd": None,
                "engineering_open_roles": None,
                "industry": None,
                "headcount_growth_pct_6m": None,
                "extra": True,
            }
        )


def test_company_field_names_match_the_model() -> None:
    """Payload trimming can only name real company fields."""
    assert frozenset(CompanyRecord.model_fields) == COMPANY_FIELD_NAMES
    assert "domain" in COMPANY_FIELD_NAMES
    assert "hiring" not in COMPANY_FIELD_NAMES
