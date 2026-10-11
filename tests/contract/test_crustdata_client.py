"""CrustdataClient against the recorded enrich response, with HTTP mocked by respx."""

import json
from decimal import Decimal

import httpx
import pytest
import respx
from pydantic import SecretStr
from tenacity import wait_none

from costwise.adapters.data.crustdata_client import ENRICH_URL, CrustdataClient
from costwise.domain.errors import DataSourceError
from tests.contract.sample import sample_body

_KEY = SecretStr("test-key")


def _client(http: httpx.Client) -> CrustdataClient:
    """Build a client that retries without waiting."""
    return CrustdataClient(http, _KEY, wait=wait_none())


@respx.mock
def test_fetch_maps_the_recorded_response_and_sends_documented_headers() -> None:
    """The sample maps to a record; auth, version, and requested fields are sent."""
    route = respx.post(ENRICH_URL).mock(return_value=httpx.Response(200, json=sample_body()))
    with httpx.Client() as http:
        fetch = _client(http).fetch("retool.com")
    assert fetch.record.domain == "retool.com"
    assert fetch.record.employee_count == 416
    assert fetch.record.funding_stage == "series_c"
    assert fetch.credits_used == Decimal(2)
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["x-api-version"] == "2025-11-01"
    sent = json.loads(request.content)
    assert sent["domains"] == ["retool.com"]
    assert "hiring" in sent["fields"]


@respx.mock
def test_fetch_drops_contact_fields_and_picks_the_best_match() -> None:
    """Contact email and phone are removed; the higher confidence match wins."""
    body = [
        {
            "matched_on": "a.com",
            "match_type": "domain",
            "matches": [
                {
                    "confidence_score": 0.2,
                    "company_data": {"basic_info": {"primary_domain": "low.com"}},
                },
                {
                    "confidence_score": 0.9,
                    "company_data": {
                        "basic_info": {"primary_domain": "a.com"},
                        "funding": {
                            "contact_email": "x@a.com",
                            "phone_number": "1",
                            "last_round_type": "seed",
                        },
                    },
                },
                "not-an-object",
            ],
        }
    ]
    respx.post(ENRICH_URL).mock(return_value=httpx.Response(200, json=body))
    with httpx.Client() as http:
        fetch = _client(http).fetch("a.com")
    assert fetch.record.domain == "a.com"
    assert fetch.raw["funding"] == {"last_round_type": "seed"}


@respx.mock
def test_server_errors_retry_then_succeed_and_then_exhaust() -> None:
    """Two 500s then 200 succeeds; three 500s raise DataSourceError."""
    route = respx.post(ENRICH_URL)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json=sample_body()),
    ]
    with httpx.Client() as http:
        assert _client(http).fetch("retool.com").record.employee_count == 416
        assert route.call_count == 3
        route.side_effect = [httpx.Response(500)] * 3
        with pytest.raises(DataSourceError, match="after retries"):
            _client(http).fetch("retool.com")


@respx.mock
def test_timeouts_retry_and_other_failures_do_not() -> None:
    """A timeout is retried; auth errors, 404, transport errors, and bad bodies are not."""
    route = respx.post(ENRICH_URL)
    route.side_effect = [httpx.ReadTimeout("slow"), httpx.Response(200, json=sample_body())]
    with httpx.Client() as http:
        client = _client(http)
        assert client.fetch("retool.com").record.domain == "retool.com"
        failures = [
            (httpx.Response(401, json={"error": {"type": "unauthorized"}}), "status 401"),
            (httpx.Response(404), "no Crustdata match"),
            (httpx.ConnectError("down"), "request failed"),
            (httpx.Response(200, content=b"not json"), "not JSON"),
            (httpx.Response(200, json={"error": "x"}), "response shape"),
            (httpx.Response(200, json=[{"matches": "x"}]), "response shape"),
            (
                httpx.Response(200, json=[{"matched_on": "a.com", "matches": []}]),
                "no Crustdata match",
            ),
        ]
        for response, message in failures:
            route.side_effect = [response]
            calls_before = route.call_count
            with pytest.raises(DataSourceError, match=message):
                client.fetch("retool.com")
            assert route.call_count == calls_before + 1


@respx.mock
def test_match_without_a_confidence_score_still_counts() -> None:
    """A match missing confidence_score is ranked at zero but still returned."""
    body = [{"matches": [{"company_data": {"basic_info": {"primary_domain": "a.com"}}}]}]
    respx.post(ENRICH_URL).mock(return_value=httpx.Response(200, json=body))
    with httpx.Client() as http:
        assert _client(http).fetch("a.com").record.domain == "a.com"
