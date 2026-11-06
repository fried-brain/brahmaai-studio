from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BrahmaAI Studio API"
    app_env: str = "development"
    database_url: str | None = None
    session_cookie_name: str = "bas_session"
    session_ttl_hours: int = 24
    secure_cookies: bool = False
    cors_origins: str = "http://localhost:3000"
    local_llm_enabled: bool = False
    local_llm_base_url: str = "http://127.0.0.1:11434"
    local_llm_model: str | None = None
    local_llm_connect_timeout_seconds: float = 3.0
    local_llm_read_timeout_seconds: float = 45.0
    local_llm_max_response_bytes: int = 1_000_000
    local_llm_max_history_messages: int = 12
    local_llm_max_history_characters: int = 12_000

    @field_validator("local_llm_base_url")
    @classmethod
    def validate_local_llm_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Local model endpoint must use http or https")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Local model endpoint must not contain credentials")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_local_llm_limits(self):
        positive = (
            self.local_llm_connect_timeout_seconds,
            self.local_llm_read_timeout_seconds,
            self.local_llm_max_response_bytes,
            self.local_llm_max_history_messages,
            self.local_llm_max_history_characters,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("Local model limits and timeouts must be positive")
        if self.local_llm_model is not None and not self.local_llm_model.strip():
            raise ValueError("Local model name cannot be blank")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
