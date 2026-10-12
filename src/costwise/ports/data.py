"""Port for fetching one company's data."""

from typing import Protocol

from costwise.domain.company import CompanyRecord
from costwise.domain.cost import Money
from costwise.domain.frozen import FrozenModel
from costwise.domain.proposals import JsonValue


class CompanyFetch(FrozenModel):
    """Normalized company, the raw payload, and credits charged for the fetch."""

    record: CompanyRecord
    raw: dict[str, JsonValue]
    credits_used: Money


class CompanyDataSource(Protocol):
    """Fetches one company by domain."""

    def fetch(self, domain: str) -> CompanyFetch:
        """Return the company payload and the credits that fetch consumed."""
        ...
