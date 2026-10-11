"""Company fetches and labels stored as JSON files."""

import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from costwise.adapters.data.crustdata_mapper import map_company
from costwise.domain.cost import Money
from costwise.domain.errors import CostwiseError, DataSourceError
from costwise.domain.frozen import FrozenModel
from costwise.domain.labels import CompanyLabel
from costwise.domain.proposals import JsonValue
from costwise.ports.data import CompanyFetch

_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
_LABELS = TypeAdapter(dict[str, CompanyLabel])
_LABELS_FILE = "labels.json"


class _StoredFetch(FrozenModel):
    """File body for one domain: the raw payload and the credits it cost."""

    credits_used: Money
    company_data: dict[str, JsonValue]


class JsonFixtureStore:
    """Writes raw/<domain>.json and labels.json under one root directory."""

    def __init__(self, root: Path) -> None:
        """Store fixtures under root."""
        self._root = root

    def save_fetch(self, domain: str, fetch: CompanyFetch) -> None:
        """Write the raw payload and credits for one domain."""
        path = self._raw_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        stored = _StoredFetch(credits_used=fetch.credits_used, company_data=fetch.raw)
        path.write_text(stored.model_dump_json(indent=2), encoding="utf-8")

    def load_fetch(self, domain: str) -> CompanyFetch:
        """Read one domain and map it to a company record."""
        path = self._raw_path(domain)
        if not path.is_file():
            raise DataSourceError(f"no fixture for {domain}")
        try:
            stored = _StoredFetch.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise DataSourceError(f"invalid fixture for {domain}") from exc
        return CompanyFetch(
            record=map_company(stored.company_data),
            raw=stored.company_data,
            credits_used=stored.credits_used,
        )

    def domains(self) -> list[str]:
        """Return stored domains in sorted order."""
        raw_dir = self._root / "raw"
        if not raw_dir.is_dir():
            return []
        return sorted(path.stem for path in raw_dir.glob("*.json"))

    def save_labels(self, labels: Mapping[str, CompanyLabel]) -> None:
        """Replace labels.json."""
        self._root.mkdir(parents=True, exist_ok=True)
        body = _LABELS.dump_json(dict(sorted(labels.items())), indent=2)
        (self._root / _LABELS_FILE).write_bytes(body)

    def load_labels(self) -> dict[str, CompanyLabel]:
        """Read labels.json."""
        path = self._root / _LABELS_FILE
        if not path.is_file():
            raise CostwiseError(f"missing fixture file: {_LABELS_FILE}")
        try:
            return _LABELS.validate_json(path.read_bytes())
        except ValidationError as exc:
            raise CostwiseError(f"invalid fixture file: {_LABELS_FILE}") from exc

    def _raw_path(self, domain: str) -> Path:
        """Return the file for a domain that cannot escape the root."""
        if _DOMAIN.fullmatch(domain) is None:
            raise DataSourceError("invalid domain")
        return self._root / "raw" / f"{domain}.json"
