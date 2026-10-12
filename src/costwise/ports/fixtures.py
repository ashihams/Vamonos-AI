"""Port for stored company fetches and their labels."""

from collections.abc import Mapping
from typing import Protocol

from costwise.domain.labels import CompanyLabel
from costwise.ports.data import CompanyFetch


class FixtureStore(Protocol):
    """Saves fetched companies once and serves them back without the network."""

    def save_fetch(self, domain: str, fetch: CompanyFetch) -> None:
        """Store the raw payload and credits for one domain."""
        ...

    def load_fetch(self, domain: str) -> CompanyFetch:
        """Return the stored fetch for one domain."""
        ...

    def domains(self) -> list[str]:
        """Return every stored domain in sorted order."""
        ...

    def save_labels(self, labels: Mapping[str, CompanyLabel]) -> None:
        """Replace the stored labels."""
        ...

    def load_labels(self) -> dict[str, CompanyLabel]:
        """Return the stored labels by domain."""
        ...
