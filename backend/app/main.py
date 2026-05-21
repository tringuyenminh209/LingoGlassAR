from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.redis import close_redis_pool, init_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await init_redis_pool(settings)
    try:
        yield
    finally:
        await close_redis_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LingoGlass Backend",
        version=settings.version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    app.include_router(health_router)
    app.include_router(sessions_router)
    return app


app = create_app()
