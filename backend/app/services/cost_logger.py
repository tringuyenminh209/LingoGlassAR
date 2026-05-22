"""Per-session cost logger and daily spend cap (S1 Day 8 — interface stub).

This file is the locked public surface for Codex to implement against in
Day 8. Dataclasses, method signatures, exceptions, and the Redis key
schema below are the contract; do not rename them. Implementation
details (pipeline vs multi, exact TTL refresh policy, etc.) are open.

Token field shape was confirmed against a real session against
``gpt-realtime`` GA on 2026-05-22 (probe commit 8d7f29f). Sample
``response.done.usage`` for one utterance::

    {
      "total_tokens": 97,
      "input_tokens": 85,
      "output_tokens": 12,
      "input_token_details": {
        "text_tokens": 46,
        "audio_tokens": 39,
        "image_tokens": 0,
        "cached_tokens": 0,
        "cached_tokens_details": {
          "text_tokens": 0,
          "audio_tokens": 0,
          "image_tokens": 0
        }
      },
      "output_token_details": {"text_tokens": 12, "audio_tokens": 0}
    }

The fixed 46-token text input is :data:`SYSTEM_INSTRUCTIONS`. There is no
``input_audio_seconds`` field on the GA event, so audio is billed by
token; the ~50 audio-tokens / second rate documented in the Realtime
API guide is only used for human-readable reporting in
:attr:`CostUsage.estimated_audio_seconds`.

Redis key schema
----------------
``session:{session_id}:cost`` — hash, TTL = parent session TTL + 600 s
    audio_input_tokens         HINCRBY       cumulative
    text_input_tokens          HINCRBY       cumulative (incl. system prompt)
    cached_audio_input_tokens  HINCRBY       cumulative
    cached_text_input_tokens   HINCRBY       cumulative
    text_output_tokens         HINCRBY       cumulative
    audio_output_tokens        HINCRBY       cumulative (always 0 today,
                                             retained for forward-compat)
    usd                        HINCRBYFLOAT  cumulative USD cost
    updated_at                 HSET          ISO-8601 UTC of last record()

``cost:daily:{YYYY-MM-DD}`` — hash, TTL = 48 h
    audio_input_tokens         HINCRBY
    text_input_tokens          HINCRBY
    cached_audio_input_tokens  HINCRBY
    cached_text_input_tokens   HINCRBY
    text_output_tokens         HINCRBY
    audio_output_tokens        HINCRBY
    usd                        HINCRBYFLOAT
    sessions                   HINCRBY       distinct session_id count

``cost:daily:{YYYY-MM-DD}:sessions`` — set, TTL = 48 h
    members: session_id strings already counted in this day's ``sessions``
    field. Used to make the per-session ``sessions`` increment idempotent
    (SADD returns 1 only on first add).

All keys live under the same redis instance the existing session metadata
uses; no separate connection pool.

Pricing
-------
USD is computed at ``record()`` time from these :class:`Settings` fields
(all are USD per million tokens, matching the OpenAI pricing-page units;
verified 2026-05-22 against the gpt-realtime GA rate sheet):

    settings.usd_per_m_audio_input        $32.00 default
    settings.usd_per_m_text_input         $ 4.00 default
    settings.usd_per_m_audio_cached_input $ 0.40 default
    settings.usd_per_m_text_cached_input  $ 0.40 default
    settings.usd_per_m_text_output        $16.00 default
    settings.usd_per_m_audio_output       $64.00 default (today unused)

Cached vs. uncached: the ``cached_*_input_tokens`` fields on
:class:`CostUsage` carry the *cached subset*, not the delta. The pricing
formula in :func:`compute_usd` bills only the non-cached remainder at the
full rate.

Privacy
-------
Per ``backend/CLAUDE.md``: never log audio bytes, translated text, source
transcripts, OpenAI session tokens, or API keys here. This module only
ever sees counts and derived USD numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from uuid import UUID


AUDIO_TOKENS_PER_SECOND = 50
"""Documented rate for OpenAI Realtime audio tokenisation (~50 / sec at
24 kHz PCM16). Used only to derive a human-readable seconds estimate; the
billing path never multiplies by this constant."""


@dataclass(frozen=True)
class CostUsage:
    """Usage delta emitted by :class:`Translator` on ``response.done``.

    Fields are cumulative for the single utterance just completed, never
    a running total. The cost logger sums them into the per-session and
    daily buckets.

    All token counts are billed at the per-million-token rates defined on
    :class:`Settings`. ``cached_*_input_tokens`` are the cached
    subset of the same input — the cost formula bills the non-cached
    remainder at the full rate and the cached subset at the cheap rate.

    Attributes
    ----------
    audio_input_tokens:
        ``input_token_details.audio_tokens`` from the response. Includes
        the cached portion (separate field below).
    text_input_tokens:
        ``input_token_details.text_tokens``. Today this is dominated by
        the 46-token :data:`SYSTEM_INSTRUCTIONS` prompt.
    cached_audio_input_tokens:
        ``input_token_details.cached_tokens_details.audio_tokens``. Zero
        on a cold session; non-zero once OpenAI prompt-caching kicks in
        for repeated audio prefixes (rare in our flow).
    cached_text_input_tokens:
        ``input_token_details.cached_tokens_details.text_tokens``. Will
        be non-zero whenever the system prompt is reused across responses
        within the same session.
    text_output_tokens:
        ``output_token_details.text_tokens`` — the translation itself.
        Equal to ``response.usage.output_tokens`` because we constrain
        ``output_modalities=["text"]``.
    audio_output_tokens:
        ``output_token_details.audio_tokens``. Always 0 today; kept on
        the schema so we never have to migrate redis hashes if we ever
        ship audio output.
    total_tokens:
        ``response.usage.total_tokens``. Stored for sanity-check
        reconciliation only; never used in the USD math.
    """

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
        """Convenience reporter for dashboards / nippo. Not used for
        billing — divide by :data:`AUDIO_TOKENS_PER_SECOND`."""
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
    """Pure pricing function. Bills the non-cached input remainder at the
    full rate and the cached subset at the cheap rate.

    Lives at module scope so unit tests can exercise it without standing
    up a redis. The :class:`CostLogger` is expected to delegate to it
    rather than re-implement the math.
    """
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
        usd_per_m_audio_input: float,
        usd_per_m_text_input: float,
        usd_per_m_audio_cached_input: float,
        usd_per_m_text_cached_input: float,
        usd_per_m_text_output: float,
        usd_per_m_audio_output: float,
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
        1. usd = compute_usd(usage, **per_million_rates)
        2. Pipeline (one round-trip):
           For each of (audio_input_tokens, text_input_tokens,
           cached_audio_input_tokens, cached_text_input_tokens,
           text_output_tokens, audio_output_tokens):
             - HINCRBY session:{id}:cost <field> <count>
             - HINCRBY cost:daily:<today> <field> <count>
           Plus:
             - HINCRBYFLOAT session:{id}:cost usd <usd>
             - HSET         session:{id}:cost updated_at <iso>
             - EXPIRE       session:{id}:cost session_ttl_seconds + 600
             - HINCRBYFLOAT cost:daily:<today> usd <usd>
             - EXPIRE       cost:daily:<today> 48*3600
             - SADD         cost:daily:<today>:sessions <session_id>
             - EXPIRE       cost:daily:<today>:sessions 48*3600
        3. If SADD returned 1, run a follow-up HINCRBY
           ``cost:daily:<today> sessions 1`` so first-touch is counted
           exactly once. The extra round-trip is acceptable because it
           only fires on the first record() of a session.
        4. Return CostRecord with the freshly-computed USD and the day
           bucket the record was written into.

        Privacy: log USD and counts at DEBUG only and never include
        session_id in pilot logs unless ``app_env == "dev"``.
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
