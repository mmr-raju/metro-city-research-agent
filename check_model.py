"""Test configured model access and structured output without displaying secrets."""
import json

from pydantic import ValidationError

from config import Settings
from llm_factory import create_llm
from nodes.common import model_error_message
from schemas import DiscoveryExtraction


def main() -> int:
    settings = Settings.from_env().model_copy(update={"max_retries": 0})
    model = create_llm(settings)
    try:
        structured = model.with_structured_output(DiscoveryExtraction.model_json_schema(), method="function_calling")
        result = structured.invoke(
            "This is a schema connectivity test with NO geographical evidence. Return cities=[], "
            "dataset_name='Unavailable', area_type='unavailable', consistent_definition=false, "
            "ranking_supported=false, ranking_basis='No evidence', population_data_note='No evidence', "
            "warnings=[], limitation='Connectivity test only'. Do not invent cities.")
        DiscoveryExtraction.model_validate_json(json.dumps(result))
        print("Model access and structured-output validation succeeded.")
        return 0
    except ValidationError as exc:
        for error in exc.errors():
            print("Invalid field:", ".".join(map(str, error["loc"])), error["type"])
        return 1
    except Exception as exc:
        print(model_error_message(exc))
        print("Model failure type:", type(exc).__name__)
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            print("HTTP status:", status)
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            detail = body.get("error", body)
            if isinstance(detail, dict):
                code = detail.get("code")
                if code in {"insufficient_quota", "invalid_api_key", "model_not_found",
                            "rate_limit_exceeded", "context_length_exceeded", "unsupported_parameter"}:
                    print("Provider error code:", code)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
