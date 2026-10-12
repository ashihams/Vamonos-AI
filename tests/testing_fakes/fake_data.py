"""Company source backed by an in-memory map."""

from collections.abc import Mapping

from costwise.domain.errors import DataSourceError
from costwise.ports.data import CompanyFetch


class FakeCompanySource:
    """Return scripted company fetches and record requested domains."""

    def __init__(self, companies: Mapping[str, CompanyFetch]) -> None:
        """Copy the company map and start an empty request log."""
        self._companies = dict(companies)
        self.domains: list[str] = []

    def fetch(self, domain: str) -> CompanyFetch:
        """Return the scripted fetch or raise DataSourceError."""
        self.domains.append(domain)
        try:
            return self._companies[domain]
        except KeyError as exc:
            raise DataSourceError(f"unknown domain: {domain}") from exc
