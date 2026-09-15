"""Read configuration lazily, so imports and offline tests need no keys."""
import os
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from errors import ConfigurationError


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    youcom_api_key: SecretStr = SecretStr("")
    youcom_base_url: str = "https://ydc-index.io"
    youcom_search_path: str = "/v1/search"
    llm_provider: str = "openai"
    llm_model: str = ""
    openai_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    search_result_count: int = Field(default=8, ge=1, le=100)
    places_per_city: int = Field(default=5, ge=1, le=20)
    http_timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=8)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        values = {
            name: os.environ[name.upper()].strip()
            for name in cls.model_fields
            if os.environ.get(name.upper(), "").strip()
        }
        try:
            settings = cls(**values)
        except ValidationError as exc:
            fields = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
            raise ConfigurationError(f"Invalid configuration: check {fields} in .env.") from None
        settings.validate_search()
        return settings

    def validate_search(self) -> None:
        if not self.youcom_api_key.get_secret_value():
            raise ConfigurationError("Set YOUCOM_API_KEY in .env before running research.")
        url = urlsplit(self.youcom_base_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ConfigurationError("YOUCOM_BASE_URL must be an HTTPS URL without credentials or query parameters.")
        if (not self.youcom_search_path.startswith("/")
                or self.youcom_search_path.startswith("//")
                or any(c in self.youcom_search_path for c in "?#")):
            raise ConfigurationError("YOUCOM_SEARCH_PATH must be a relative endpoint path such as /v1/search.")
