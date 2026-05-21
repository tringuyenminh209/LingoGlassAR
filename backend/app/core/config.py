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
