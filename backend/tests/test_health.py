import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
async def test_healthz_returns_ok_with_redis_state() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() in (
        {"status": "ok", "version": "0.1.0", "redis": "up"},
        {"status": "ok", "version": "0.1.0", "redis": "down"},
    )
