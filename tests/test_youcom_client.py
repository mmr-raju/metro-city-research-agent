import httpx
import pytest

from clients.youcom_client import YouComClient
from errors import (SearchAuthenticationError, SearchNetworkError, SearchRateLimitError,
                    SearchResponseError)


def payload():
    return {"results": {"web": [
        {"title": "First", "url": "https://example.com/a?utm_source=test", "description": "Description",
         "snippets": ["Supporting fact"]},
        {"title": "Duplicate", "url": "https://example.com/a", "snippets": []}], "news": []}}


def test_post_auth_normalization_deduplication(settings):
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/search"
        assert request.headers["X-API-Key"] == "test-only"
        assert b'"count":8' in request.content
        return httpx.Response(200, json=payload())
    with YouComClient(settings, transport=httpx.MockTransport(handler)) as client:
        rows = client.search("test")
    assert len(rows) == 1
    assert str(rows[0].url) == "https://example.com/a?utm_source=test"
    assert "Supporting fact" in rows[0].snippet
    assert rows[0].publisher == "example.com"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retry_then_success(status, settings):
    responses = iter([httpx.Response(status), httpx.Response(status), httpx.Response(200, json=payload())])
    sleeps = []
    with YouComClient(settings.model_copy(update={"max_retries": 2}),
                      transport=httpx.MockTransport(lambda _: next(responses)), sleep=sleeps.append) as client:
        assert client.search("test")
    assert sleeps == [1, 2]


@pytest.mark.parametrize("status,error", [(401, SearchAuthenticationError), (403, SearchAuthenticationError),
    (429, SearchRateLimitError), (503, SearchNetworkError), (422, SearchResponseError)])
def test_safe_errors(status, error, settings):
    with YouComClient(settings, transport=httpx.MockTransport(lambda _: httpx.Response(status, text="SECRET"))) as client:
        with pytest.raises(error) as exc:
            client.search("test")
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize("data", [{}, {"results": []}, {"results": {"web": "bad"}},
                                   {"results": {"web": [{"url": "bad"}]}}])
def test_malformed_response(data, settings):
    with YouComClient(settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))) as client:
        with pytest.raises(SearchResponseError):
            client.search("test")


def test_network_failure(settings):
    def fail(request):
        raise httpx.ConnectError("secret request information", request=request)
    with YouComClient(settings, transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(SearchNetworkError, match="connectivity"):
            client.search("test")


def test_wrong_endpoint_has_actionable_error(settings):
    with YouComClient(settings, transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        with pytest.raises(SearchResponseError, match="YOUCOM_BASE_URL=https://ydc-index.io"):
            client.search("test")
