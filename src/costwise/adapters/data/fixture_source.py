"""Company data source that reads stored fixtures instead of calling Crustdata."""

from costwise.ports.data import CompanyFetch
from costwise.ports.fixtures import FixtureStore


class FixtureCompanySource:
    """Return the stored payload and the credits measured when it was fetched."""

    def __init__(self, store: FixtureStore) -> None:
        """Read companies from the store."""
        self._store = store

    def fetch(self, domain: str) -> CompanyFetch:
        """Return the stored fetch for the domain."""
        return self._store.load_fetch(domain)
