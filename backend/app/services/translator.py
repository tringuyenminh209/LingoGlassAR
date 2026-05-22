"""OpenAI Realtime translator service - interface contract (S1 Day 2).

Design decisions locked here (Codex implements against this, does not
rename or rewrite the public surface):

1. Streaming generator (`AsyncIterator[TextDelta]`) over callback. Aligns
   with the FastAPI WS bridge planned for S1 Day 3 and keeps the
   backpressure model simple - the consumer pulls.
2. One WS per `Translator` instance. The caller owns the lifecycle via
   the async context manager. Concurrent `translate_stream()` calls on
   the same instance are not supported (one utterance at a time).
3. `TextDelta` carries incremental chunks AND a `final` marker. Renderers
   can paint as they go and commit on `final=True`.
4. Source-language transcription text rides on a separate field
   (`source_text`) so the S1 Day 8 cost logger can attribute usage
   without the BLE renderer caring. Never log this value - privacy
   boundary from backend/CLAUDE.md.
5. OpenAI `error` events become `TranslatorError`. Do not swallow.

Codex: implementation details (which SDK call, framing strategy,
reconnect behaviour) are yours. Only the public API below is locked.
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import AsyncIterator

import websockets

from app.services.cost_logger import CostUsage

logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTIONS = (
    "You are a JP<->VN translator. When you receive Japanese audio, "
    "output Vietnamese text only. When you receive Vietnamese audio, "
    "output Japanese text only. No commentary, no romanization."
)

# GA Realtime model. The earlier `gpt-4o-realtime-preview` only accepted the
# beta API shape (flat `input_audio_format`, `modalities`, `OpenAI-Beta` header)
# which OpenAI disabled in 2026 with error
# `invalid_request_error.beta_api_shape_disabled`. The GA shape (nested
# `audio.input.format` object, `output_modalities`, `session.type`) is now the
# only accepted shape, and `gpt-realtime` is the matching GA model.
DEFAULT_MODEL = "gpt-realtime"


@dataclass(frozen=True)
class TextDelta:
    """One incremental output from the translator.

    Attributes
    ----------
    text:
        Incremental translated text. May be empty (e.g. on the closing
        delta where the only meaningful field is ``final=True``).
    final:
        True iff this is the closing delta for the current utterance
        (maps to OpenAI ``response.text.done``). Renderers should commit
        the buffered text when ``final`` is True.
    source_text:
        Optional transcription of the source-language audio. Present
        only when OpenAI emits
        ``conversation.item.input_audio_transcription.completed``.
        Consumed by the S1 Day 8 cost logger; the BLE renderer ignores
        it. Never log this value.
    usage:
        Token / audio counts for the just-completed response. Populated
        only on the closing delta (``final=True``) when OpenAI emits a
        ``response.done`` event with a usage block. ``None`` when the
        response ended without a usage report (legacy alias path, mock
        WS in tests, or stream cut after ``response.output_text.done``).
    """

    text: str
    final: bool = False
    source_text: str | None = None
    usage: CostUsage | None = None


class TranslatorError(RuntimeError):
    """Raised when the OpenAI Realtime session signals an error event
    or the underlying WebSocket fails non-recoverably.

    Transient transport hiccups (a dropped frame, momentary backpressure)
    should be handled inside the implementation and not surface here.
    """


class Translator:
    """Async client for the OpenAI Realtime API tuned for JP<->VN.

    Lifecycle
    ---------
    ::

        async with Translator(api_key=settings.openai_api_key) as t:
            async for delta in t.translate_stream(audio_frames):
                if delta.text:
                    await ws_to_mobile.send_json({"text": delta.text})
                if delta.final:
                    break

    The instance owns a single WebSocket to
    ``wss://api.openai.com/v1/realtime?model=<model>``. To translate two
    utterances in parallel, instantiate two Translators.

    Audio format
    ------------
    Input frames are raw PCM16 mono LE at **24 kHz** (matches OpenAI
    Realtime API's ``pcm16`` input format exactly so the bytes are
    forwarded verbatim — no server-side resampling). Frame size is
    caller's choice; ~100 ms (4800 bytes) is recommended. Frames are
    forwarded to OpenAI as ``input_audio_buffer.append`` events.

    Session prompt
    --------------
    A fixed ``session.update`` with :data:`SYSTEM_INSTRUCTIONS` is sent
    on connect using the GA shape (``session.type = "realtime"``, nested
    ``audio.input.format`` object, ``output_modalities = ["text"]``).
    ``audio.input.transcription`` must be enabled so we get the
    source-language text on :attr:`TextDelta.source_text`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._ws = None
        self._streaming = False

    async def __aenter__(self) -> "Translator":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        """Open the WebSocket and send the initial session configuration.

        Idempotent: calling on an already-connected instance is a no-op.
        """
        if self._ws is not None:
            return

        url = f"wss://api.openai.com/v1/realtime?model={self._model}"
        try:
            # GA Realtime requires no OpenAI-Beta header. Sending it produces
            # `beta_api_shape_disabled`. session.update payload uses the GA
            # shape: explicit `type:"realtime"`, `output_modalities` (not
            # `modalities`), and a nested `audio.input` object whose `format`
            # is an object (`audio/pcm` + sample rate), not the old string.
            self._ws = await websockets.connect(
                url,
                extra_headers={
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            await self._send_json(
                {
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "output_modalities": ["text"],
                        "instructions": SYSTEM_INSTRUCTIONS,
                        "audio": {
                            "input": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": 24000,
                                },
                                "transcription": {"model": "whisper-1"},
                            },
                        },
                    },
                }
            )
        except Exception as exc:
            self._ws = None
            raise TranslatorError("failed to connect to OpenAI Realtime") from exc

    async def close(self) -> None:
        """Close the WebSocket. Safe to call multiple times."""
        ws = self._ws
        self._ws = None
        self._streaming = False
        if ws is not None:
            await ws.close()

    async def translate_stream(
        self,
        audio_frames: AsyncIterator[bytes],
    ) -> AsyncIterator[TextDelta]:
        """Stream-translate one utterance.

        Consumes ``audio_frames`` until the iterator is exhausted (the
        caller signals end-of-utterance by closing the iterator),
        commits the input buffer to OpenAI, then yields
        :class:`TextDelta` items as the model responds. The async
        generator ends after a delta with ``final=True`` (or raises on
        error).

        Raises
        ------
        TranslatorError
            If OpenAI emits an ``error`` event or the WebSocket fails
            non-recoverably.
        RuntimeError
            If called before :meth:`connect` or outside the context
            manager.
        """
        if self._ws is None:
            raise RuntimeError("Translator is not connected")
        if self._streaming:
            raise RuntimeError("Translator already has an active stream")

        self._streaming = True
        try:
            async for frame in audio_frames:
                await self._send_json(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(frame).decode("ascii"),
                    }
                )

            await self._send_json({"type": "input_audio_buffer.commit"})
            # S1 Day 8 probe — confirms the commit/create sequence reached
            # the broker. No payload bytes logged.
            logger.info("realtime.audio_committed model=%s", self._model)
            # GA `response.create` uses `output_modalities` to mirror the
            # session-level field; `modalities` is rejected.
            await self._send_json(
                {
                    "type": "response.create",
                    "response": {
                        "output_modalities": ["text"],
                        "instructions": SYSTEM_INSTRUCTIONS,
                    },
                }
            )

            output_text_done = False
            finalized = False

            async for raw_event in self._ws:
                event = _decode_event(raw_event)
                event_type = event.get("type")
                # S1 Day 8 probe — log only the event type so we can see
                # which response.* arrive in real traffic. Removed once
                # response.done usage shape is locked.
                logger.info("realtime.event type=%s", event_type)

                # GA renamed the text streaming events
                # (`response.text.*` -> `response.output_text.*`). Accept the
                # old names too in case OpenAI keeps a legacy alias for a
                # transition window.
                if event_type in (
                    "response.output_text.delta",
                    "response.text.delta",
                ):
                    yield TextDelta(text=str(event.get("delta", "")))
                elif event_type in (
                    "response.output_text.done",
                    "response.text.done",
                ):
                    # Defer the final yield until ``response.done`` so we can
                    # attach usage. The trailing fallback below covers the
                    # case where ``response.done`` never arrives.
                    output_text_done = True
                elif event_type == "response.done":
                    usage = _extract_usage(event)
                    # S1 Day 8 probe — confirm GA usage shape AND raw
                    # token-detail counts so the cost_logger pricing model
                    # can be locked. All values are integer counts; no
                    # transcript or audio content is logged.
                    response_obj = event.get("response")
                    raw_usage = (
                        response_obj.get("usage")
                        if isinstance(response_obj, dict)
                        else None
                    )
                    logger.info(
                        "realtime.response.done usage=%s raw_usage=%s",
                        usage,
                        raw_usage,
                    )
                    finalized = True
                    yield TextDelta(text="", final=True, usage=usage)
                    return
                elif (
                    event_type
                    == "conversation.item.input_audio_transcription.completed"
                ):
                    transcript = event.get("transcript")
                    if isinstance(transcript, str):
                        yield TextDelta(text="", source_text=transcript)
                elif event_type == "error":
                    raise TranslatorError(_error_message(event))

            # Stream ended without ``response.done``. Emit the final delta so
            # the consumer's loop terminates cleanly; usage stays ``None``.
            if output_text_done and not finalized:
                yield TextDelta(text="", final=True)
        except TranslatorError:
            raise
        except Exception as exc:
            raise TranslatorError(
                f"OpenAI Realtime WebSocket failed: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            self._streaming = False

    async def _send_json(self, payload: dict[str, object]) -> None:
        if self._ws is None:
            raise RuntimeError("Translator is not connected")
        await self._ws.send(json.dumps(payload))


def _decode_event(raw_event: str | bytes) -> dict[str, object]:
    if isinstance(raw_event, bytes):
        raw_event = raw_event.decode("utf-8")
    try:
        event = json.loads(raw_event)
    except json.JSONDecodeError as exc:
        raise TranslatorError("OpenAI Realtime returned invalid JSON") from exc
    if not isinstance(event, dict):
        raise TranslatorError("OpenAI Realtime returned a non-object event")
    return event


def _error_message(event: dict[str, object]) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    return "OpenAI Realtime error"


def _safe_keys(obj: object) -> list[str] | None:
    """Return a sorted list of keys for shape logging, or ``None``.

    Used by the S1 Day 8 probe to log only the structure of OpenAI events
    without their values. Counts and durations are safe; transcripts and
    audio bytes are not, so the rest of the event is never logged.
    """
    if isinstance(obj, dict):
        return sorted(obj.keys())
    return None


def _extract_usage(event: dict[str, object]) -> CostUsage | None:
    """Best-effort parser for the GA ``response.done`` usage block.

    Falls back gracefully when fields are absent or shaped differently;
    the probe log in :meth:`Translator.translate_stream` will surface any
    surprise so we can tighten this before Codex ships the cost logger.
    """
    response = event.get("response")
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None

    tokens_in = _int_or_zero(usage.get("input_tokens"))
    tokens_out = _int_or_zero(usage.get("output_tokens"))

    explicit_seconds = usage.get("input_audio_seconds")
    if isinstance(explicit_seconds, (int, float)):
        audio_seconds = float(explicit_seconds)
    else:
        details = usage.get("input_token_details")
        audio_tokens = (
            details.get("audio_tokens") if isinstance(details, dict) else None
        )
        # Placeholder rate: ~50 audio tokens / second per OpenAI Realtime
        # docs. The Day 8 probe confirms (or refutes) this on real traffic.
        audio_seconds = (
            float(audio_tokens) / 50.0 if isinstance(audio_tokens, int) else 0.0
        )

    return CostUsage(
        audio_seconds=audio_seconds,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0
