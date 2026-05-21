from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "dev"
    log_level: str = "info"
    cors_origins: Annotated[list[str], NoDecode] = ["*"]
    public_base_url: str = "ws://localhost:8000"
    redis_pool_size: int = 10
    version: str = "0.1.0"

    # S1 Day 8 cost logger / daily cap. Pricing defaults are placeholders
    # carried over from the OpenAI Realtime preview pricing page and must
    # be reconciled with the GA rate sheet before the pilot. Setting
    # daily_usd_cap to 0 disables the cap check (dev / load-test mode).
    daily_usd_cap: float = 5.0
    usd_per_audio_minute_input: float = 0.10
    usd_per_1k_tokens_in: float = 0.005
    usd_per_1k_tokens_out: float = 0.020

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
