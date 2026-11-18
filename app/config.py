
"""Configuration module using pydantic-settings to manage environment variables."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core App
    APP_NAME: str = "AI-Powered Website Link Analysis API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 4000

    # LLM Provider
    LLM_PROVIDER: Literal["gemini", "openai", "mock"] = "gemini"

    # Google Gemini Settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"

    # OpenAI Settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Crawler & Network Settings
    REQUEST_TIMEOUT: int = 15
    MAX_CONTENT_LENGTH: int = 25000
    MAX_REDIRECTS: int = 5
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
        "(DXORA-LinkAnalyzer/1.0)"
    )

    # Caching Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600


settings = Settings()
