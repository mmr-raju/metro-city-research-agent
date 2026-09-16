import json
from collections.abc import Callable
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from clients.youcom_client import deduplicate
from config import Settings
from errors import ModelError, SearchAuthenticationError, SearchError
from schemas import SearchResult

T = TypeVar("T", bound=BaseModel)
Progress = Callable[[str], None]


def model_error_message(exc: Exception) -> str:
    """Translate common SDK failures without exposing request bodies or credentials."""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    code = detail.get("code") if isinstance(detail, dict) else None
    if status == 401:
        return ("The model provider rejected the API key (HTTP 401). Replace the API key for your "
                "selected LLM_PROVIDER in .env, then restart Streamlit. Do not share the key in chat.")
    if status == 403:
        return "The model provider denied access (HTTP 403). Check your API key permissions and account access."
    if status == 404 or code == "model_not_found":
        return "The configured LLM_MODEL was not found or is unavailable to this account. Check the model name and account access."
    if code == "insufficient_quota" or status == 402:
        return "The model account has insufficient API credits or quota. Check provider billing and usage limits."
    if status == 429:
        return "The model provider rate limit was reached (HTTP 429). Wait and retry, or check account usage limits."
    if code == "context_length_exceeded":
        return "The search evidence exceeds the model context limit. Lower SEARCH_RESULT_COUNT or select a model with a larger context window."
    if status in {400, 422}:
        return "The model rejected the structured-output request. Check that LLM_MODEL supports function calling and temperature zero."
    if isinstance(status, int) and status >= 500:
        return "The model provider is temporarily unavailable. Retry in a few minutes."
    if "connection" in type(exc).__name__.lower() or "timeout" in type(exc).__name__.lower():
        return "Could not connect to the model provider. Check network access and HTTP_TIMEOUT_SECONDS, then retry."
    if isinstance(exc, ValidationError):
        return "The model response did not match the required report fields. Retry research or select a model with stronger structured-output support."
    return "The model could not produce a valid structured response. Check LLM_MODEL and function-calling support, then retry."


def extract(llm: BaseChatModel, schema: type[T], prompt: str, data: dict,
            *, progress: Progress | None = None) -> T:
    notify = progress or (lambda message: None)
    try:
        # A JSON-schema envelope returns a dictionary. Validate as JSON ourselves:
        # strict Pydantic datetime fields must accept JSON timestamp strings, while
        # the default PydanticToolsParser validates Python kwargs instead.
        structured = llm.with_structured_output(schema.model_json_schema(), method="function_calling")
        notify("LLM: Calling model to extract a structured result from retrieved evidence.")
        result = structured.invoke([SystemMessage(content=prompt),
                                    HumanMessage(content=json.dumps(data, ensure_ascii=False))])
        # JSON validation permits JSON URL/datetime strings while preserving strict numbers.
        validated = result if isinstance(result, schema) else schema.model_validate_json(json.dumps(result))
    except Exception as exc:
        notify("LLM: Failed to produce a valid structured result.")
        raise ModelError(model_error_message(exc)) from None
    notify("LLM: Completed structured extraction; evidence checks follow.")
    return validated


def run_searches(search: BaseTool, queries: list[str], settings: Settings,
                 *, progress: Progress | None = None) -> tuple[list[SearchResult], list[str]]:
    notify = progress or (lambda message: None)
    results: list[SearchResult] = []
    warnings: list[str] = []
    for index, query in enumerate(queries, 1):
        label = f"You.com search {index}/{len(queries)}"
        notify(f"{label}: Calling live search — {query}")
        try:
            response = search.invoke({"query": query, "count": settings.search_result_count})
            rows = [SearchResult.model_validate_json(json.dumps(row)) for row in response]
            results.extend(rows)
        except SearchAuthenticationError:
            notify(f"{label}: Failed — check search account access or credits.")
            raise
        except SearchError as exc:
            notify(f"{label}: Failed — continuing with the remaining searches.")
            warnings.append(f"Search incomplete for '{query}': {exc}")
        except Exception:
            notify(f"{label}: Failed — search results could not be processed.")
            raise
        else:
            notify(f"{label}: Completed — {len(rows)} results returned.")
    return deduplicate(results), warnings
