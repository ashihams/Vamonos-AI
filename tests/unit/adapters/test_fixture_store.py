"""JSON fixture store and the fixture company source."""

from decimal import Decimal
from pathlib import Path

import pytest

from costwise.adapters.data.crustdata_mapper import map_company
from costwise.adapters.data.fixture_source import FixtureCompanySource
from costwise.adapters.data.fixture_store import JsonFixtureStore
from costwise.domain.errors import CostwiseError, DataSourceError
from costwise.domain.labels import CompanyLabel
from costwise.domain.task import Difficulty, Split
from costwise.ports.data import CompanyFetch
from tests.contract.sample import sample_company


def _fetch() -> CompanyFetch:
    """Build a fetch from the recorded sample."""
    company = sample_company()
    return CompanyFetch(record=map_company(company), raw=company, credits_used=Decimal("2"))


def test_fetch_and_labels_round_trip(tmp_path: Path) -> None:
    """Stored fetches reload with the same record, payload, and credits; labels too."""
    store = JsonFixtureStore(tmp_path)
    assert store.domains() == []
    store.save_fetch("retool.com", _fetch())
    assert store.domains() == ["retool.com"]
    loaded = FixtureCompanySource(store).fetch("retool.com")
    assert loaded == _fetch()
    assert '"credits_used": "2"' in (tmp_path / "raw" / "retool.com.json").read_text("utf-8")

    labels = {
        "retool.com": CompanyLabel(expected_fit=True, difficulty=Difficulty.EASY, split=Split.EVAL)
    }
    store.save_labels(labels)
    assert store.load_labels() == labels


def test_store_errors(tmp_path: Path) -> None:
    """Bad domains, missing files, and corrupt files raise typed errors."""
    store = JsonFixtureStore(tmp_path)
    with pytest.raises(DataSourceError, match="invalid domain"):
        store.save_fetch("../escape", _fetch())
    with pytest.raises(DataSourceError, match="no fixture"):
        store.load_fetch("missing.com")
    with pytest.raises(CostwiseError, match="missing fixture file"):
        store.load_labels()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "bad.com.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataSourceError, match="invalid fixture"):
        store.load_fetch("bad.com")
    (tmp_path / "labels.json").write_text("[]", encoding="utf-8")
    with pytest.raises(CostwiseError, match="invalid fixture file"):
        store.load_labels()
