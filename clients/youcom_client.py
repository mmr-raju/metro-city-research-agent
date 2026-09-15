"""You.com POST Search client. No scraping and no raw responses sent to the model."""
import time
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from config import Settings
from errors import (SearchAuthenticationError, SearchError, SearchNetworkError,
                    SearchRateLimitError, SearchResponseError)
from schemas import SearchResult

RETRY_STATUSES = {429, 500, 502, 503, 504}


def canonical_url(url: str) -> str:
    """Only a deduplication key: returned citation URLs are never rewritten."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/",
                       urlencode(sorted(query)), ""))


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique = []
    for result in results:
        key = canonical_url(str(result.url))
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


class YouComClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        settings.validate_search()
        self.settings = settings
        self.sleep = sleep
        self._client = httpx.Client(
            base_url=settings.youcom_base_url.rstrip("/"),
            headers={"X-API-Key": settings.youcom_api_key.get_secret_value()},
            timeout=settings.http_timeout_seconds, transport=transport,
            follow_redirects=False,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._client.close()

    def search(self, query: str, count: int = 8) -> list[SearchResult]:
        if not query.strip() or type(count) is not int or not 1 <= count <= 100:
            raise SearchError("Search requires a nonempty query and count between 1 and 100.")
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self._client.post(self.settings.youcom_search_path,
                                             json={"query": query, "count": count})
            except httpx.RequestError:
                if attempt < self.settings.max_retries:
                    self.sleep(2 ** attempt)
                    continue
                raise SearchNetworkError("Search connection failed. Check connectivity and retry.") from None
            status = response.status_code
            if status in {401, 403}:
                raise SearchAuthenticationError("You.com authentication failed. Check YOUCOM_API_KEY and account access.")
            if status == 402:
                raise SearchAuthenticationError("You.com requires available account credits. Check your account billing.")
            if status in RETRY_STATUSES:
                if attempt < self.settings.max_retries:
                    self.sleep(2 ** attempt)
                    continue
                if status == 429:
                    raise SearchRateLimitError("You.com rate limit reached. Wait briefly and retry.")
                raise SearchNetworkError("You.com is temporarily unavailable. Retry in a few minutes.")
            if not response.is_success:
                if status == 404:
                    raise SearchResponseError(
                        "You.com search endpoint was not found (HTTP 404). Set YOUCOM_BASE_URL=https://ydc-index.io "
                        "and YOUCOM_SEARCH_PATH=/v1/search in .env, then restart Streamlit.")
                raise SearchResponseError(f"You.com rejected the search request (HTTP {status}). Check the configured endpoint and API access.")
            try:
                return self._normalize(response.json())
            except (ValueError, TypeError, KeyError, ValidationError):
                raise SearchResponseError("You.com returned an unexpected response format. Retry or check the Search API configuration.") from None
        raise SearchNetworkError("Search could not complete. Retry later.")

    @staticmethod
    def _normalize(data: dict) -> list[SearchResult]:
        if not isinstance(data, dict) or not isinstance(data.get("results"), dict):
            raise ValueError("Missing results object")
        sections = data["results"]
        if not any(k in sections for k in ("web", "news")):
            raise ValueError("Missing search sections")
        rows = []
        for section in ("web", "news"):
            entries = sections.get(section, [])
            if not isinstance(entries, list):
                raise ValueError("Invalid section")
            rows.extend(entries)
        results = []
        accessed = datetime.now(timezone.utc)
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid result")
            snippets = row.get("snippets", [])
            description = row.get("description", "")
            if not isinstance(snippets, list) or not all(isinstance(s, str) for s in snippets):
                raise ValueError("Invalid snippets")
            if not isinstance(description, str):
                raise ValueError("Invalid description")
            pieces = list(dict.fromkeys([description, *snippets]))
            results.append(SearchResult(
                title=row["title"], url=row["url"],
                snippet="\n".join(s for s in pieces if s),
                publisher=row.get("publisher") or urlsplit(row["url"]).hostname,
                published_at=row.get("published_at") or row.get("page_age"),
                accessed_at=accessed,
            ))
        return deduplicate(results)
