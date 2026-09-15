"""Exercise both real LangChain adapters with mocked SDK responses, without network."""
from types import SimpleNamespace

import pytest

from config import Settings
from evidence import audit_report
from llm_factory import create_llm
from nodes.common import extract
from schemas import CityReport
from conftest import bundle_for, report_for


@pytest.mark.parametrize("provider", ["openai", "groq"])
def test_actual_adapter_parses_strict_report(provider, monkeypatch, cities, population_result):
    report = audit_report(report_for(cities[0]), cities[0], bundle_for(cities[0]), [population_result])
    model = create_llm(Settings(llm_provider=provider, llm_model="test-model",
                                openai_api_key="test-only", groq_api_key="test-only"))
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return {"id": "test-completion", "object": "chat.completion", "created": 1,
                "model": "test-model", "choices": [{"index": 0, "finish_reason": "tool_calls",
                    "message": {"role": "assistant", "content": None, "tool_calls": [
                        {"id": "test-call", "type": "function", "function": {
                            "name": "CityReport", "arguments": report.model_dump_json()}}]}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    monkeypatch.setattr(model.client, "create", create)
    # ChatOpenAI uses the SDK's raw-response wrapper; ChatGroq uses create directly.
    if hasattr(model.client, "with_raw_response"):
        monkeypatch.setattr(model.client.with_raw_response, "create",
                            lambda **kwargs: SimpleNamespace(parse=lambda: create(**kwargs), headers={}))
    result = extract(model, CityReport, "Extract supplied evidence only.", {"evidence": "test"})
    assert result == report
    assert result.sources[0].accessed_at == population_result.accessed_at
    assert requests[0]["tools"][0]["function"]["name"] == "CityReport"
    assert "test-only" not in str(requests[0]["messages"])


@pytest.mark.parametrize("status,code,expected", [
    (401, "invalid_api_key", "rejected the API key"),
    (403, None, "denied access"),
    (404, "model_not_found", "LLM_MODEL"),
    (429, "insufficient_quota", "credits or quota"),
    (429, "rate_limit_exceeded", "rate limit"),
    (400, "context_length_exceeded", "context limit"),
    (400, "unsupported_parameter", "function calling"),
    (503, None, "temporarily unavailable"),
])
def test_model_errors_are_actionable_and_redacted(status, code, expected):
    from errors import ModelError

    class BrokenModel:
        def with_structured_output(self, *args, **kwargs):
            error = RuntimeError("Secret credential and raw request details must not appear")
            error.status_code = status
            error.body = {"error": {"code": code, "message": "Secret credential"}}
            raise error

    with pytest.raises(ModelError, match=expected) as caught:
        extract(BrokenModel(), CityReport, "Test", {})
    assert "Secret" not in str(caught.value)
