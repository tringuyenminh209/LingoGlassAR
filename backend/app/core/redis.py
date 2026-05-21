from collections.abc import AsyncIterator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import Settings, get_settings

_pool: ConnectionPool | None = None


async def init_redis_pool(settings: Settings | None = None) -> None:
    global _pool
    if _pool is not None:
        return
    settings = settings or get_settings()
    _pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_pool_size,
        decode_responses=True,
    )


async def close_redis_pool() -> None:
    global _pool
    pool = _pool
    _pool = None
    if pool is not None:
        await pool.aclose()


async def get_redis() -> AsyncIterator[Redis]:
    if _pool is None:
        await init_redis_pool()
    if _pool is None:
        raise RuntimeError("Redis pool is not initialized")
    client = Redis(connection_pool=_pool)
    try:
        yield client
    finally:
        await client.aclose()
