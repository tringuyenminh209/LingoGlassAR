from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import translate as translate_api
from app.core.config import Settings, get_settings
from app.core.redis import get_redis
from app.main import create_app
from app.services.cost_logger import CostUsage, DailyStats
from app.services.translator import TextResult, TranslatorError
from tests.fakes import FakeRedis


USAGE = CostUsage(
    audio_input_tokens=0,
    text_input_tokens=12,
    cached_audio_input_tokens=0,
    cached_text_input_tokens=0,
    text_output_tokens=7,
    audio_output_tokens=0,
    total_tokens=19,
)


class TrackingCostLogger:
    def __init__(self, *, daily_usd: float = 0.0) -> None:
        self.daily_usd = daily_usd
        self.records: list[tuple[UUID, CostUsage]] = []

    async def daily(self, day: date | None = None) -> DailyStats:
        return DailyStats(
            day=day or datetime.now(UTC).date(),
            usd=self.daily_usd,
            audio_input_tokens=0,
            text_input_tokens=0,
            cached_audio_input_tokens=0,
            cached_text_input_tokens=0,
            text_output_tokens=0,
            audio_output_tokens=0,
            sessions=0,
        )

    async def record(self, request_id: UUID, usage: CostUsage) -> None:
        self.records.append((request_id, usage))


def make_app(cost_logger: TrackingCostLogger, settings: Settings | None = None):
    app = create_app()

    async def override_get_redis():
        yield FakeRedis()

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[translate_api.get_cost_logger] = lambda: cost_logger
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    return app


def request_body(text: str = "source text") -> dict[str, str]:
    return {
        "sourceLang": "ja",
        "targetLang": "vi",
        "text": text,
    }


def patch_translator(
    monkeypatch,
    *,
    result: TextResult | None = None,
    error: TranslatorError | None = None,
) -> list[object]:
    instances: list[object] = []

    class FakeChatTranslator:
        def __init__(self, *, api_key: str, model: str) -> None:
            self.api_key = api_key
            self.model = model
            instances.append(self)

        async def translate(self, text: str) -> TextResult:
            if error is not None:
                raise error
            assert result is not None
            return result

    monkeypatch.setattr(translate_api, "ChatTranslator", FakeChatTranslator)
    return instances


@pytest.mark.asyncio
async def test_translate_returns_text_duration_and_records_usage(monkeypatch) -> None:
    cost_logger = TrackingCostLogger()
    patch_translator(
        monkeypatch,
        result=TextResult(translated_text="translated text", usage=USAGE),
    )
    transport = ASGITransport(app=make_app(cost_logger))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/translate", json=request_body())

    assert response.status_code == 200
    assert response.json()["success"] is True
    data = response.json()["data"]
    assert data["translatedText"] == "translated text"
    assert isinstance(data["durationMs"], int)
    assert data["durationMs"] >= 0
    assert len(cost_logger.records) == 1
    assert cost_logger.records[0][1] == USAGE


@pytest.mark.asyncio
async def test_translate_returns_daily_cap_exceeded_when_cap_is_reached() -> None:
    cost_logger = TrackingCostLogger(daily_usd=0.001)
    settings = Settings(daily_usd_cap=0.0001)
    transport = ASGITransport(app=make_app(cost_logger, settings))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/translate", json=request_body())

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "daily_cap_exceeded"


@pytest.mark.asyncio
async def test_translate_maps_translator_error_to_502(
    monkeypatch,
) -> None:
    instances = patch_translator(
        monkeypatch,
        error=TranslatorError("upstream failed"),
    )
    transport = ASGITransport(app=make_app(TrackingCostLogger()))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/translate", json=request_body())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "translator_error"
    assert len(instances) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"sourceLang": "ja", "targetLang": "vi"},
        request_body(""),
        request_body("x" * 2001),
        {"sourceLang": "en", "targetLang": "vi", "text": "source text"},
    ],
)
async def test_translate_rejects_invalid_body(body: dict[str, str]) -> None:
    transport = ASGITransport(app=make_app(TrackingCostLogger()))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/translate", json=body)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_translate_does_not_log_source_or_translated_text(
    monkeypatch,
    caplog,
) -> None:
    source_text = "private source marker"
    translated_text = "private translation marker"
    patch_translator(
        monkeypatch,
        result=TextResult(translated_text=translated_text, usage=USAGE),
    )
    transport = ASGITransport(app=make_app(TrackingCostLogger()))
    caplog.set_level(logging.INFO)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/translate", json=request_body(source_text))

    assert response.status_code == 200
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert source_text not in log_text
    assert translated_text not in log_text
