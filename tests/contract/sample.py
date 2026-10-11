"""The trimmed real Crustdata enrich response for retool.com, fetched 2026-10-11."""

import json
from pathlib import Path

from costwise.domain.proposals import JsonValue

SAMPLE_PATH = Path(__file__).parent / "data" / "crustdata_enrich_retool.json"


def sample_body() -> list[dict[str, JsonValue]]:
    """Return the full response body as parsed JSON."""
    body: list[dict[str, JsonValue]] = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return body


def sample_company() -> dict[str, JsonValue]:
    """Return company_data from the single match."""
    matches = sample_body()[0]["matches"]
    assert isinstance(matches, list)
    first = matches[0]
    assert isinstance(first, dict)
    company = first["company_data"]
    assert isinstance(company, dict)
    return company
