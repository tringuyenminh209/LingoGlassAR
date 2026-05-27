"""Per-session cost logger and daily spend cap.

Redis key schema
----------------
``session:{session_id}:cost`` is a hash with parent session TTL + 600 s:
``audio_input_tokens``, ``text_input_tokens``,
``cached_audio_input_tokens``, ``cached_text_input_tokens``,
``text_output_tokens``, ``audio_output_tokens``, ``usd``, ``updated_at``.

``cost:daily:{YYYY-MM-DD}`` is a 48-hour hash with the same six token
fields plus ``usd`` and the distinct-session ``sessions`` counter.
``cost:daily:{YYYY-MM-DD}:sessions`` is a 48-hour set of session IDs
already counted in the daily ``sessions`` field.

Cached input fields are subsets of input counts. Non-cached input uses
the full price; cached input uses the cached price. This module only
stores counts and derived USD values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date as date_cls
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis


AUDIO_TOKENS_PER_SECOND = 50

_TOKEN_FIELDS = (
    "audio_input_tokens",
    "text_input_tokens",
    "cached_audio_input_tokens",
    "cached_text_input_tokens",
    "text_output_tokens",
    "audio_output_tokens",
)
_DAILY_TTL_SECONDS = 48 * 3600


@dataclass(frozen=True)
class CostUsage:
    audio_input_tokens: int
    text_input_tokens: int
    cached_audio_input_tokens: int
    cached_text_input_tokens: int
    text_output_tokens: int
    audio_output_tokens: int
    total_tokens: int

    @classmethod
    def zero(cls) -> "CostUsage":
        return cls(
            audio_input_tokens=0,
            text_input_tokens=0,
            cached_audio_input_tokens=0,
            cached_text_input_tokens=0,
            text_output_tokens=0,
            audio_output_tokens=0,
            total_tokens=0,
        )

    @property
    def estimated_audio_seconds(self) -> float:
        return self.audio_input_tokens / float(AUDIO_TOKENS_PER_SECOND)


def compute_usd(
    usage: CostUsage,
    *,
    usd_per_m_audio_input: float,
    usd_per_m_text_input: float,
    usd_per_m_audio_cached_input: float,
    usd_per_m_text_cached_input: float,
    usd_per_m_text_output: float,
    usd_per_m_audio_output: float,
) -> float:
    raw_audio = max(0, usage.audio_input_tokens - usage.cached_audio_input_tokens)
    raw_text = max(0, usage.text_input_tokens - usage.cached_text_input_tokens)
    return (
        raw_audio * usd_per_m_audio_input
        + raw_text * usd_per_m_text_input
        + usage.cached_audio_input_tokens * usd_per_m_audio_cached_input
        + usage.cached_text_input_tokens * usd_per_m_text_cached_input
        + usage.text_output_tokens * usd_per_m_text_output
        + usage.audio_output_tokens * usd_per_m_audio_output
    ) / 1_000_000.0


@dataclass(frozen=True)
class CostRecord:
    session_id: UUID
    usage: CostUsage
    usd: float
    day: date_cls
    recorded_at: datetime


@dataclass(frozen=True)
class DailyStats:
    day: date_cls
    usd: float
    audio_input_tokens: int
    text_input_tokens: int
    cached_audio_input_tokens: int
    cached_text_input_tokens: int
    text_output_tokens: int
    audio_output_tokens: int
    sessions: int

    @property
    def estimated_audio_seconds(self) -> float:
        return self.audio_input_tokens / float(AUDIO_TOKENS_PER_SECOND)


class DailyCapExceeded(RuntimeError):
    def __init__(self, current_usd: float, cap_usd: float) -> None:
        super().__init__(
            f"daily spend {current_usd:.4f} USD has reached cap {cap_usd:.2f} USD"
        )
        self.current_usd = current_usd
        self.cap_usd = cap_usd


class CostLogger:
    """Writes per-session and daily cost buckets to redis."""

    def __init__(
        self,
        redis: Redis,
        *,
        usd_per_m_audio_input: float,
        usd_per_m_text_input: float,
        usd_per_m_audio_cached_input: float,
        usd_per_m_text_cached_input: float,
        usd_per_m_text_output: float,
        usd_per_m_audio_output: float,
        daily_usd_cap: float,
        session_ttl_seconds: int = 3600,
    ) -> None:
        self.redis = redis
        self.usd_per_m_audio_input = usd_per_m_audio_input
        self.usd_per_m_text_input = usd_per_m_text_input
        self.usd_per_m_audio_cached_input = usd_per_m_audio_cached_input
        self.usd_per_m_text_cached_input = usd_per_m_text_cached_input
        self.usd_per_m_text_output = usd_per_m_text_output
        self.usd_per_m_audio_output = usd_per_m_audio_output
        self.daily_usd_cap = daily_usd_cap
        self.session_ttl_seconds = session_ttl_seconds

    async def record(
        self,
        session_id: UUID,
        usage: CostUsage,
        *,
        now: datetime | None = None,
    ) -> CostRecord:
        recorded_at = now or datetime.now(UTC)
        day = recorded_at.date()
        day_key = _daily_key(day)
        session_key = _session_cost_key(session_id)
        sessions_key = f"{day_key}:sessions"
        usd = compute_usd(usage, **self._rates())

        pipe = self.redis.pipeline()
        for field in _TOKEN_FIELDS:
            pipe.hincrby(session_key, field, getattr(usage, field))
        pipe.hincrbyfloat(session_key, "usd", usd)
        pipe.hset(session_key, "updated_at", recorded_at.isoformat())
        pipe.expire(session_key, self.session_ttl_seconds + 600)
        for field in _TOKEN_FIELDS:
            pipe.hincrby(day_key, field, getattr(usage, field))
        pipe.hincrbyfloat(day_key, "usd", usd)
        pipe.expire(day_key, _DAILY_TTL_SECONDS)
        pipe.sadd(sessions_key, str(session_id))
        pipe.expire(sessions_key, _DAILY_TTL_SECONDS)
        results = await pipe.execute()

        if results[-2] == 1:
            first_touch_pipe = self.redis.pipeline()
            first_touch_pipe.hincrby(day_key, "sessions", 1)
            await first_touch_pipe.execute()

        return CostRecord(
            session_id=session_id,
            usage=usage,
            usd=usd,
            day=day,
            recorded_at=recorded_at,
        )

    async def session_cost(self, session_id: UUID) -> CostRecord | None:
        fields = await self.redis.hgetall(_session_cost_key(session_id))
        if not fields:
            return None

        recorded_at = datetime.fromisoformat(_hash_str(fields, "updated_at"))
        return CostRecord(
            session_id=session_id,
            usage=_usage_from_hash(fields),
            usd=_hash_float(fields, "usd"),
            day=recorded_at.astimezone(UTC).date(),
            recorded_at=recorded_at,
        )

    async def daily(self, day: date_cls | None = None) -> DailyStats:
        day = day or datetime.now(UTC).date()
        fields = await self.redis.hgetall(_daily_key(day))
        return DailyStats(
            day=day,
            usd=_hash_float(fields, "usd"),
            audio_input_tokens=_hash_int(fields, "audio_input_tokens"),
            text_input_tokens=_hash_int(fields, "text_input_tokens"),
            cached_audio_input_tokens=_hash_int(fields, "cached_audio_input_tokens"),
            cached_text_input_tokens=_hash_int(fields, "cached_text_input_tokens"),
            text_output_tokens=_hash_int(fields, "text_output_tokens"),
            audio_output_tokens=_hash_int(fields, "audio_output_tokens"),
            sessions=_hash_int(fields, "sessions"),
        )

    def _rates(self) -> dict[str, float]:
        return {
            "usd_per_m_audio_input": self.usd_per_m_audio_input,
            "usd_per_m_text_input": self.usd_per_m_text_input,
            "usd_per_m_audio_cached_input": self.usd_per_m_audio_cached_input,
            "usd_per_m_text_cached_input": self.usd_per_m_text_cached_input,
            "usd_per_m_text_output": self.usd_per_m_text_output,
            "usd_per_m_audio_output": self.usd_per_m_audio_output,
        }


async def enforce_daily_cap(
    cost_logger: CostLogger,
    *,
    cap_usd: float,
    now: datetime | None = None,
) -> None:
    if cap_usd <= 0:
        return

    stats = await cost_logger.daily(day=(now or datetime.now(UTC)).date())
    if stats.usd >= cap_usd:
        raise DailyCapExceeded(current_usd=stats.usd, cap_usd=cap_usd)


def _session_cost_key(session_id: UUID) -> str:
    return f"session:{session_id}:cost"


def _daily_key(day: date_cls) -> str:
    return f"cost:daily:{day.isoformat()}"


def _usage_from_hash(fields: dict[object, object]) -> CostUsage:
    token_counts = {field: _hash_int(fields, field) for field in _TOKEN_FIELDS}
    return CostUsage(
        **token_counts,
        total_tokens=sum(token_counts.values()),
    )


def _hash_value(fields: dict[object, object], field: str) -> object | None:
    if field in fields:
        return fields[field]
    return fields.get(field.encode())


def _hash_int(fields: dict[object, object], field: str) -> int:
    value = _hash_value(fields, field)
    return int(value) if value is not None else 0


def _hash_float(fields: dict[object, object], field: str) -> float:
    value = _hash_value(fields, field)
    return float(value) if value is not None else 0.0


def _hash_str(fields: dict[object, object], field: str) -> str:
    value = _hash_value(fields, field)
    if value is None:
        raise KeyError(field)
    if isinstance(value, bytes):
        return value.decode()
    return str(value)
