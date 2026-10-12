"""Mapping a Crustdata company_data object to a CompanyRecord."""

import pytest

from costwise.adapters.data.crustdata_mapper import map_company
from costwise.domain.errors import DataSourceError
from tests.contract.sample import sample_company


def test_recorded_sample_maps_every_field() -> None:
    """The real retool.com response fills every CompanyRecord field."""
    record = map_company(sample_company())
    assert record.domain == "retool.com"
    assert record.employee_count == 416
    assert record.funding_stage == "series_c"
    assert record.total_funding_usd == 141_000_000
    assert record.engineering_open_roles == 3
    assert record.industry == "Software Development"
    assert record.headcount_growth_pct_6m == pytest.approx(-3.480278422273782)


def test_missing_and_mistyped_fields_become_none() -> None:
    """Absent sections, wrong types, booleans, fractions, and empty text map to None."""
    company = sample_company()
    company["headcount"] = {"total": True, "growth_percent": "n/a"}
    company["funding"] = {"total_investment_usd": 1.5, "last_round_type": ""}
    del company["hiring"]
    company["taxonomy"] = ["not", "an", "object"]
    record = map_company(company)
    assert record.employee_count is None
    assert record.headcount_growth_pct_6m is None
    assert record.total_funding_usd is None
    assert record.funding_stage is None
    assert record.engineering_open_roles is None
    assert record.industry is None


def test_missing_domain_raises() -> None:
    """A company without a primary domain cannot be keyed."""
    with pytest.raises(DataSourceError, match="primary domain"):
        map_company({"basic_info": {"name": "No Domain"}})
