"""Fixture store kept in memory."""

from collections.abc import Mapping

from costwise.domain.errors import CostwiseError, DataSourceError
from costwise.domain.labels import CompanyLabel
from costwise.ports.data import CompanyFetch


class InMemoryFixtureStore:
    """Keep fetches and labels in dictionaries."""

    def __init__(self, fetches: Mapping[str, CompanyFetch] | None = None) -> None:
        """Start with optional stored fetches and no labels."""
        self.fetches: dict[str, CompanyFetch] = dict(fetches or {})
        self.labels: dict[str, CompanyLabel] | None = None

    def save_fetch(self, domain: str, fetch: CompanyFetch) -> None:
        """Store one fetch."""
        self.fetches[domain] = fetch

    def load_fetch(self, domain: str) -> CompanyFetch:
        """Return one fetch or raise DataSourceError."""
        try:
            return self.fetches[domain]
        except KeyError as exc:
            raise DataSourceError(f"no fixture for {domain}") from exc

    def domains(self) -> list[str]:
        """Return stored domains in sorted order."""
        return sorted(self.fetches)

    def save_labels(self, labels: Mapping[str, CompanyLabel]) -> None:
        """Replace the labels."""
        self.labels = dict(labels)

    def load_labels(self) -> dict[str, CompanyLabel]:
        """Return the labels or raise when none were saved."""
        if self.labels is None:
            raise CostwiseError("missing fixture file: labels.json")
        return dict(self.labels)
