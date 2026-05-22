from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis import get_redis
from app.main import create_app
from app.services.cost_logger import CostUsage
from tests.fakes import FakeRedis
from tests.test_cost_logger import make_logger


def make_app(fake_redis: FakeRedis):
    app = create_app()

    async def override_get_redis() -> AsyncIterator[FakeRedis]:
        yield fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    return app


@pytest.mark.asyncio
async def test_stats_returns_zero_day_without_traffic() -> None:
    transport = ASGITransport(app=make_app(FakeRedis()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/stats?days=1")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]["days"]) == 1
    assert body["data"]["days"][0]["usd"] == 0.0


@pytest.mark.asyncio
async def test_stats_reflects_recorded_daily_usage() -> None:
    fake_redis = FakeRedis()
    await make_logger(fake_redis).record(
        uuid4(),
        CostUsage(
            audio_input_tokens=10,
            text_input_tokens=46,
            cached_audio_input_tokens=0,
            cached_text_input_tokens=0,
            text_output_tokens=5,
            audio_output_tokens=0,
            total_tokens=61,
        ),
    )

    transport = ASGITransport(app=make_app(fake_redis))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/stats?days=1")

    assert response.status_code == 200
    today = response.json()["data"]["days"][0]
    assert today["audio_input_tokens"] == 10
    assert today["text_input_tokens"] == 46
    assert today["text_output_tokens"] == 5
    assert today["sessions"] == 1
    assert today["usd"] > 0


@pytest.mark.asyncio
async def test_stats_rejects_out_of_range_days() -> None:
    transport = ASGITransport(app=make_app(FakeRedis()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/stats?days=3")

    assert response.status_code == 422
