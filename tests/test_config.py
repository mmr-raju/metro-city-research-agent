import pytest

from config import Settings
from errors import ConfigurationError
from llm_factory import create_llm


def test_unsupported_provider():
    with pytest.raises(ConfigurationError, match="Unsupported LLM_PROVIDER"):
        create_llm(Settings(llm_provider="unknown"))


@pytest.mark.parametrize("provider", ["openai", "groq"])
def test_missing_provider_key(provider):
    with pytest.raises(ConfigurationError, match=f"{provider.upper()}_API_KEY"):
        create_llm(Settings(llm_provider=provider, llm_model="test-model"))


def test_missing_search_key():
    with pytest.raises(ConfigurationError, match="YOUCOM_API_KEY"):
        Settings().validate_search()


def test_missing_model():
    with pytest.raises(ConfigurationError, match="LLM_MODEL"):
        create_llm(Settings())


@pytest.mark.parametrize("provider", ["openai", "groq"])
def test_provider_instantiates_without_network(provider):
    from langchain_core.language_models import BaseChatModel
    model = create_llm(Settings(llm_provider=provider, llm_model="test-model",
                               openai_api_key="test-only", groq_api_key="test-only"))
    assert isinstance(model, BaseChatModel)


def test_keys_are_redacted_in_settings_repr():
    assert "never-display-this" not in repr(Settings(youcom_api_key="never-display-this"))
