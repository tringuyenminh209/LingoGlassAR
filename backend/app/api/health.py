from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.redis import get_redis

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    redis: Literal["up", "down"]


async def _redis_state(redis: Redis) -> Literal["up", "down"]:
    try:
        return "up" if await redis.ping() else "down"
    except Exception:
        return "down"


@router.get("/healthz", response_model=HealthResponse)
async def healthz(redis: Redis = Depends(get_redis)) -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.version,
        redis=await _redis_state(redis),
    )
