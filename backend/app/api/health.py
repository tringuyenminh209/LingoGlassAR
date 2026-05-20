from typing import Literal

import redis.asyncio as redis
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    redis: Literal["up", "down"]


async def _redis_state(redis_url: str) -> Literal["up", "down"]:
    client = redis.from_url(redis_url)
    try:
        return "up" if await client.ping() else "down"
    except Exception:
        return "down"
    finally:
        await client.aclose()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.version,
        redis=await _redis_state(settings.redis_url),
    )
