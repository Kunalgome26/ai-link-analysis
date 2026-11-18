"""Configuration module using pydantic-settings to manage environment variables."""

import os
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

    # LLM Provider: 'gemini', 'openai', or 'mock'
    LLM_PROVIDER: Literal["gemini", "openai", "mock"] = "gemini"

    # Google Gemini Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Crawler & Network Settings
    REQUEST_TIMEOUT: int = 15  # seconds
    MAX_CONTENT_LENGTH: int = 25000  # characters
    MAX_REDIRECTS: int = 5
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (DXORA-LinkAnalyzer/1.0)"
    )

    # Caching Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600  # 1 hour in-memory cache


settings = Settings()
