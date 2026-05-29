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

    # S3 OCR translate model. The OCR path is one-shot text->text, so it uses
    # chat completions (a single HTTP request) instead of the Realtime WS the
    # speech path uses - opening a Realtime WS per capture cost ~4 s of
    # handshake and blew the OCR latency gate (S3 Day 6 bench).
    translate_model: str = "gpt-4o-mini"

    # S1 Day 8 cost logger / daily cap. Per-million-token rates for the
    # ``gpt-realtime`` GA model, captured 2026-05-22 from OpenAI's
    # pricing page. Setting daily_usd_cap to 0 disables the cap check
    # (dev / load-test mode).
    daily_usd_cap: float = 5.0
    usd_per_m_audio_input: float = 32.0
    usd_per_m_text_input: float = 4.0
    usd_per_m_audio_cached_input: float = 0.40
    usd_per_m_text_cached_input: float = 0.40
    usd_per_m_text_output: float = 16.0
    usd_per_m_audio_output: float = 64.0

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
