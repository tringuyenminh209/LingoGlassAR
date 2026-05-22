from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.cost_logger import (
    CostLogger,
    CostUsage,
    DailyCapExceeded,
    compute_usd,
    enforce_daily_cap,
)
from tests.fakes import FakeRedis


def rates() -> dict[str, float]:
    settings = Settings()
    return {
        "usd_per_m_audio_input": settings.usd_per_m_audio_input,
        "usd_per_m_text_input": settings.usd_per_m_text_input,
        "usd_per_m_audio_cached_input": settings.usd_per_m_audio_cached_input,
        "usd_per_m_text_cached_input": settings.usd_per_m_text_cached_input,
        "usd_per_m_text_output": settings.usd_per_m_text_output,
        "usd_per_m_audio_output": settings.usd_per_m_audio_output,
    }


def make_logger(redis: FakeRedis) -> CostLogger:
    return CostLogger(redis, daily_usd_cap=5.0, **rates())


def usage(
    *,
    audio_input: int = 0,
    text_input: int = 0,
    cached_audio: int = 0,
    cached_text: int = 0,
    text_output: int = 0,
    audio_output: int = 0,
) -> CostUsage:
    return CostUsage(
        audio_input_tokens=audio_input,
        text_input_tokens=text_input,
        cached_audio_input_tokens=cached_audio,
        cached_text_input_tokens=cached_text,
        text_output_tokens=text_output,
        audio_output_tokens=audio_output,
        total_tokens=audio_input + text_input + text_output + audio_output,
    )


def test_compute_usd_all_non_cached_input() -> None:
    assert compute_usd(usage(audio_input=100, text_input=50), **rates()) == pytest.approx(
        (100 * 32.0 + 50 * 4.0) / 1_000_000
    )


def test_compute_usd_all_cached_input() -> None:
    amount = compute_usd(
        usage(audio_input=100, text_input=50, cached_audio=100, cached_text=50),
        **rates(),
    )
    assert amount == pytest.approx((100 * 0.40 + 50 * 0.40) / 1_000_000)


def test_compute_usd_mixed_cached_audio() -> None:
    amount = compute_usd(
        usage(audio_input=100, cached_audio=25, text_output=10),
        **rates(),
    )
    assert amount == pytest.approx((75 * 32.0 + 25 * 0.40 + 10 * 16.0) / 1_000_000)


def test_compute_usd_zero_usage() -> None:
    assert compute_usd(CostUsage.zero(), **rates()) == 0.0


@pytest.mark.asyncio
async def test_record_updates_session_and_daily_hashes_once_per_session() -> None:
    redis = FakeRedis()
    logger = make_logger(redis)
    session_id = uuid4()
    recorded_at = datetime(2026, 5, 22, 1, 2, tzinfo=UTC)
    delta = usage(
        audio_input=10,
        text_input=46,
        cached_text=20,
        text_output=5,
    )

    first = await logger.record(session_id, delta, now=recorded_at)
    await logger.record(session_id, delta, now=recorded_at)

    session_key = f"session:{session_id}:cost"
    daily_key = "cost:daily:2026-05-22"
    expected_fields = {
        "audio_input_tokens",
        "text_input_tokens",
        "cached_audio_input_tokens",
        "cached_text_input_tokens",
        "text_output_tokens",
        "audio_output_tokens",
    }
    assert {field for name, field, _ in redis.hincrby_calls if name == session_key} >= (
        expected_fields
    )
    assert {field for name, field, _ in redis.hincrby_calls if name == daily_key} >= (
        expected_fields | {"sessions"}
    )
    assert redis.hashes[daily_key]["sessions"] == "1"
    assert redis.hashes[session_key]["audio_input_tokens"] == "20"
    assert redis.hashes[daily_key]["text_output_tokens"] == "10"
    assert first.day.isoformat() == "2026-05-22"
    assert first.usd > 0

    cumulative = await logger.session_cost(session_id)
    assert cumulative is not None
    assert cumulative.usage.total_tokens == 162


@pytest.mark.asyncio
async def test_daily_returns_zero_stats_for_missing_bucket() -> None:
    stats = await make_logger(FakeRedis()).daily(datetime(2026, 5, 22, tzinfo=UTC).date())

    assert stats.usd == 0.0
    assert stats.audio_input_tokens == 0
    assert stats.sessions == 0


@pytest.mark.asyncio
async def test_enforce_daily_cap_raises_at_or_above_cap() -> None:
    redis = FakeRedis()
    redis.hashes["cost:daily:2026-05-22"] = {"usd": "0.001"}
    logger = make_logger(redis)

    with pytest.raises(DailyCapExceeded) as exc:
        await enforce_daily_cap(
            logger,
            cap_usd=0.0001,
            now=datetime(2026, 5, 22, tzinfo=UTC),
        )

    assert exc.value.current_usd == 0.001
    assert exc.value.cap_usd == 0.0001
