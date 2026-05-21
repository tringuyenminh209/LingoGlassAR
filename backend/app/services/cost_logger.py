"""Per-session cost logger and daily spend cap (S1 Day 8 — interface stub).

This file is the locked public surface for Codex to implement against in
Day 8. Dataclasses, method signatures, exceptions, and the Redis key
schema below are the contract; do not rename them. Implementation
details (pipeline vs multi, exact TTL refresh policy, etc.) are open.

Redis key schema
----------------
``session:{session_id}:cost`` — hash, TTL = parent session TTL + 600 s
    audio_seconds  HINCRBYFLOAT  cumulative seconds of input audio
    tokens_in      HINCRBY       cumulative input tokens (text + audio)
    tokens_out     HINCRBY       cumulative output tokens
    usd            HINCRBYFLOAT  cumulative USD cost
    updated_at     HSET          ISO-8601 UTC of last record()

``cost:daily:{YYYY-MM-DD}`` — hash, TTL = 48 h
    audio_seconds  HINCRBYFLOAT
    tokens_in      HINCRBY
    tokens_out     HINCRBY
    usd            HINCRBYFLOAT
    sessions       HINCRBY       count of distinct session_ids in this bucket

``cost:daily:{YYYY-MM-DD}:sessions`` — set, TTL = 48 h
    members: session_id strings already counted in this day's ``sessions``
    field. Used to make the per-session ``sessions`` increment idempotent
    (SADD returns 1 only on first add).

All keys live under the same redis instance the existing session metadata
uses; no separate connection pool.

Pricing
-------
USD is computed at ``record()`` time from these :class:`Settings` fields:

    settings.usd_per_audio_minute_input  - input audio billed by minute
    settings.usd_per_1k_tokens_in        - input tokens (text + audio)
    settings.usd_per_1k_tokens_out       - output tokens (text)

Defaults are placeholders. Final values must be verified against the
OpenAI Realtime GA pricing page before the S5 pilot. The S1 Day 8 probe
in :func:`app.services.translator.Translator.translate_stream` logs the
raw ``response.done`` usage shape so we can confirm field names.

Privacy
-------
Per ``backend/CLAUDE.md``: never log audio bytes, translated text, source
transcripts, OpenAI session tokens, or API keys here. This module only
ever sees counts, durations, and derived USD numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CostUsage:
    """Usage delta emitted by :class:`Translator` on ``response.done``.

    Fields are cumulative for the single utterance just completed, never
    a running total. The cost logger sums them into the per-session and
    daily buckets.

    Attributes
    ----------
    audio_seconds:
        Duration of input audio billed by OpenAI for this utterance. The
        Realtime GA event currently reports audio as a token count in
        ``input_token_details.audio_tokens``; the translator converts to
        seconds before populating this field. If OpenAI later adds an
        explicit ``input_audio_seconds`` field, the translator switches
        to it transparently.
    tokens_in:
        Total input tokens (``response.usage.input_tokens``) including
        the audio-tokenised input. Logged separately from ``audio_seconds``
        so we can sanity-check the conversion rate.
    tokens_out:
        Total output tokens (``response.usage.output_tokens``); text-only
        because :data:`SYSTEM_INSTRUCTIONS` constrains the session to
        ``output_modalities = ["text"]``.
    """

    audio_seconds: float
    tokens_in: int
    tokens_out: int

    @classmethod
    def zero(cls) -> "CostUsage":
        return cls(audio_seconds=0.0, tokens_in=0, tokens_out=0)


@dataclass(frozen=True)
class CostRecord:
    """Result of a single :meth:`CostLogger.record` call.

    Returned so the caller can echo back the computed USD (e.g. attach to
    a debug WS frame in dev builds) without an extra redis round-trip.
    """

    session_id: UUID
    usage: CostUsage
    usd: float
    day: date_cls
    recorded_at: datetime


@dataclass(frozen=True)
class DailyStats:
    """Aggregated daily figures returned by ``GET /v1/stats``."""

    day: date_cls
    usd: float
    audio_seconds: float
    tokens_in: int
    tokens_out: int
    sessions: int


class DailyCapExceeded(RuntimeError):
    """Raised by :func:`enforce_daily_cap` when today's spend has reached
    or exceeded :attr:`Settings.daily_usd_cap`.

    The session-creation endpoint catches this and returns HTTP 429 with
    ``error.code = "daily_cap_exceeded"`` per the API contract.
    """

    def __init__(self, current_usd: float, cap_usd: float) -> None:
        super().__init__(
            f"daily spend {current_usd:.4f} USD has reached cap {cap_usd:.2f} USD"
        )
        self.current_usd = current_usd
        self.cap_usd = cap_usd


class CostLogger:
    """Writes per-session and daily cost buckets to redis.

    One instance per request is fine; the redis client is pooled at the
    app level. The logger does not hold per-session state across calls.
    """

    def __init__(
        self,
        redis: object,  # redis.asyncio.Redis — typed `object` to keep this
                        # stub import-light. Codex tightens the annotation.
        *,
        usd_per_audio_minute_input: float,
        usd_per_1k_tokens_in: float,
        usd_per_1k_tokens_out: float,
        daily_usd_cap: float,
        session_ttl_seconds: int = 3600,
    ) -> None:
        raise NotImplementedError("S1 Day 8 — Codex implements")

    async def record(
        self,
        session_id: UUID,
        usage: CostUsage,
        *,
        now: datetime | None = None,
    ) -> CostRecord:
        """Persist one usage delta and return the computed record.

        Steps (Codex pseudocode):
        1. Compute USD = audio_seconds / 60 * usd_per_audio_minute_input
                       + tokens_in / 1000 * usd_per_1k_tokens_in
                       + tokens_out / 1000 * usd_per_1k_tokens_out
        2. Pipeline:
           - HINCRBYFLOAT session:{id}:cost audio_seconds <secs>
           - HINCRBY      session:{id}:cost tokens_in <n>
           - HINCRBY      session:{id}:cost tokens_out <n>
           - HINCRBYFLOAT session:{id}:cost usd <usd>
           - HSET         session:{id}:cost updated_at <iso>
           - EXPIRE       session:{id}:cost session_ttl_seconds + 600
           - SADD         cost:daily:<today>:sessions <session_id>
           - HINCRBYFLOAT cost:daily:<today> audio_seconds <secs>
           - HINCRBY      cost:daily:<today> tokens_in <n>
           - HINCRBY      cost:daily:<today> tokens_out <n>
           - HINCRBYFLOAT cost:daily:<today> usd <usd>
           - EXPIRE       cost:daily:<today> 48*3600
           - EXPIRE       cost:daily:<today>:sessions 48*3600
        3. If SADD returned 1, also HINCRBY cost:daily:<today> sessions 1.
           Do this in a second pipeline so step 2 stays single-trip; the
           extra hop only happens on the first record() of a session.
        4. Return CostRecord with computed values.

        Privacy: do not log the usage object or USD if log level is INFO;
        use DEBUG only and never include session_id in pilot logs unless
        ``app_env == "dev"``.
        """
        raise NotImplementedError("S1 Day 8 — Codex implements")

    async def session_cost(self, session_id: UUID) -> CostRecord | None:
        """Return the cumulative record for one session, or ``None`` if no
        cost has been recorded (key absent or fully expired).

        Used by latency-suite tooling in Day 9; not exposed on the public
        API.
        """
        raise NotImplementedError("S1 Day 8 — Codex implements")

    async def daily(self, day: date_cls | None = None) -> DailyStats:
        """Read one day's bucket. ``day=None`` means today (UTC).

        Returns zero-filled :class:`DailyStats` if the bucket key is
        absent (never written or expired).
        """
        raise NotImplementedError("S1 Day 8 — Codex implements")


async def enforce_daily_cap(
    cost_logger: CostLogger,
    *,
    cap_usd: float,
    now: datetime | None = None,
) -> None:
    """Read today's bucket and raise :class:`DailyCapExceeded` if at cap.

    ``cap_usd <= 0`` disables the check (returns immediately). Called
    from ``POST /v1/sessions`` before allocating a new session_id.

    The check is racy: two concurrent session creations can both observe
    a value below the cap and both pass. That is acceptable for a
    single-tenant prototype; tightening to a CAS / lua script is S2+.
    """
    raise NotImplementedError("S1 Day 8 — Codex implements")
