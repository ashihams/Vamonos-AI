"""Crustdata company enrich over HTTPS."""

from decimal import Decimal

import httpx
from pydantic import SecretStr, TypeAdapter
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.wait import wait_base

from costwise.adapters.data.crustdata_mapper import map_company
from costwise.domain.errors import DataSourceError
from costwise.domain.proposals import JsonValue
from costwise.ports.data import CompanyFetch

ENRICH_URL = "https://api.crustdata.com/company/enrich"
API_VERSION = "2025-11-01"
ENRICH_FIELDS = ("basic_info", "headcount", "funding", "hiring", "taxonomy")
# TODO(VERIFY: Crustdata credits charged per company enrich call)
CREDITS_PER_ENRICH = Decimal(2)
TIMEOUT_SECONDS = 10.0
_ATTEMPTS = 3
_OK = 200
_NOT_FOUND = 404
_SERVER_ERROR = 500
_CONTACT_KEYS = frozenset({"contact_email", "phone_number"})
_OBJECT = TypeAdapter(dict[str, JsonValue])


class _TransientError(Exception):
    """A server error or timeout that may succeed on retry."""


class CrustdataClient:
    """Fetch one company from POST /company/enrich, retrying server errors and timeouts."""

    def __init__(
        self, http: httpx.Client, api_key: SecretStr, wait: wait_base | None = None
    ) -> None:
        """Use the given HTTP client and key; wait controls the pause between retries."""
        self._http = http
        self._api_key = api_key
        self._wait = wait if wait is not None else wait_exponential(multiplier=0.5, max=4)

    def fetch(self, domain: str) -> CompanyFetch:
        """Return the best match for the domain without company contact fields."""
        company = _best_match(_decode(self._post_with_retry(domain)), domain)
        cleaned = _without_contact_fields(company)
        return CompanyFetch(
            record=map_company(cleaned),
            raw=cleaned,
            credits_used=CREDITS_PER_ENRICH,
        )

    def _post_with_retry(self, domain: str) -> httpx.Response:
        """Post up to three times when the failure is transient."""
        retrying = Retrying(
            stop=stop_after_attempt(_ATTEMPTS),
            wait=self._wait,
            retry=retry_if_exception_type(_TransientError),
            reraise=True,
        )
        try:
            return retrying(self._post_once, domain)
        except _TransientError as exc:
            raise DataSourceError("Crustdata request failed after retries") from exc

    def _post_once(self, domain: str) -> httpx.Response:
        """Post once and classify the failure."""
        try:
            response = self._http.post(
                ENRICH_URL,
                headers={
                    "authorization": f"Bearer {self._api_key.get_secret_value()}",
                    "x-api-version": API_VERSION,
                },
                json={"domains": [domain], "fields": list(ENRICH_FIELDS)},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise _TransientError("timeout") from exc
        except httpx.HTTPError as exc:
            raise DataSourceError("Crustdata request failed") from exc
        return _checked(response, domain)


def _checked(response: httpx.Response, domain: str) -> httpx.Response:
    """Return a 200 response or raise the matching error."""
    status = response.status_code
    if status >= _SERVER_ERROR:
        raise _TransientError(f"status {status}")
    if status == _NOT_FOUND:
        raise DataSourceError(f"no Crustdata match for {domain}")
    if status != _OK:
        raise DataSourceError(f"Crustdata returned status {status}")
    return response


def _decode(response: httpx.Response) -> object:
    """Parse the JSON body."""
    try:
        body: object = response.json()
    except ValueError as exc:
        raise DataSourceError("Crustdata response is not JSON") from exc
    return body


def _best_match(body: object, domain: str) -> dict[str, JsonValue]:
    """Return company_data from the highest-confidence match for the first identifier."""
    if not isinstance(body, list) or not body or not isinstance(body[0], dict):
        raise DataSourceError("unexpected Crustdata response shape")
    matches = body[0].get("matches")
    if not isinstance(matches, list):
        raise DataSourceError("unexpected Crustdata response shape")
    candidates = [
        match
        for match in matches
        if isinstance(match, dict) and isinstance(match.get("company_data"), dict)
    ]
    if not candidates:
        raise DataSourceError(f"no Crustdata match for {domain}")
    best = max(candidates, key=_confidence)
    return _OBJECT.validate_python(best["company_data"])


def _confidence(match: dict[str, object]) -> float:
    """Return the match confidence, or zero when it is missing."""
    score = match.get("confidence_score")
    if isinstance(score, bool) or not isinstance(score, int | float):
        return 0.0
    return float(score)


def _without_contact_fields(company: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Drop the funding contact email and phone so fixtures hold no contact details."""
    funding = company.get("funding")
    if not isinstance(funding, dict):
        return company
    kept: dict[str, JsonValue] = {
        key: value for key, value in funding.items() if key not in _CONTACT_KEYS
    }
    return {**company, "funding": kept}
