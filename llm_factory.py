"""The sole provider-specific part of the workflow."""
from langchain_core.language_models import BaseChatModel

from config import Settings
from errors import ConfigurationError


def create_llm(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.strip().lower()
    if provider not in {"openai", "groq"}:
        raise ConfigurationError("Unsupported LLM_PROVIDER. Choose 'openai' or 'groq'.")
    if not settings.llm_model:
        raise ConfigurationError("Set LLM_MODEL to a chat model supporting tool/function calling.")
    key = settings.openai_api_key if provider == "openai" else settings.groq_api_key
    if not key.get_secret_value():
        raise ConfigurationError(f"Set {provider.upper()}_API_KEY for the selected provider.")
    common = dict(model=settings.llm_model, api_key=key.get_secret_value(),
                  temperature=0, timeout=settings.http_timeout_seconds,
                  max_retries=settings.max_retries)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(**common)
    from langchain_groq import ChatGroq
    return ChatGroq(**common)
