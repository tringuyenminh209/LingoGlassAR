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
from typing import AsyncIterator, Literal

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


TranscriptionDelay = Literal["minimal", "low", "medium", "high", "xhigh"]


@dataclass(frozen=True)
class STTConfig:
    """Tunables for the speech-to-text leg of the Realtime session.

    Defaults reflect the S2 Day 1 probe decision (see
    ``docs/reports/S2_stt_probe.md``):

    - ``transcription_model = "gpt-realtime-whisper"`` replaces the S1
      default ``"whisper-1"``. The newer model is streaming-first with
      OpenAI-quoted partial latency 200-400 ms vs. whisper-1's
      finished-audio orientation.
    - ``transcription_delay = "low"`` favours latency over WER. Valid
      values: ``minimal`` / ``low`` / ``medium`` / ``high`` / ``xhigh``.
      Only honoured when ``transcription_model == "gpt-realtime-whisper"``.

    Codex (Day 2 body impl): wire both fields into the
    ``audio.input.transcription`` block of the ``session.update`` payload
    in :meth:`Translator.connect`. Do NOT rename fields or add new ones
    here; if a tuning knob needs to change, extend this dataclass and
    re-prep on Day 3 with a fresh probe row.
    """

    transcription_model: str = "gpt-realtime-whisper"
    transcription_delay: TranscriptionDelay = "low"


DEFAULT_STT_CONFIG = STTConfig()


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

    STT tuning (S2 Day 2)
    ---------------------
    ``stt_config`` (defaults to :data:`DEFAULT_STT_CONFIG`) controls the
    transcription model + delay sent inside ``audio.input.transcription``.
    Default values are the S2 Day 1 probe target (``gpt-realtime-whisper``
    + ``delay="low"``). Pass a non-default ``STTConfig`` only for A/B
    benchmarking; production callers should accept the default so they
    benefit from future probe updates without code changes.

    S2 Day 2 body changes for Codex (do these in :meth:`connect` only,
    not in :meth:`translate_stream`):

    1. ``audio.input.transcription`` becomes
       ``{"model": stt_config.transcription_model,
       "delay": stt_config.transcription_delay}``.
    2. Add ``"turn_detection": None`` at the top level of ``session``
       to disable server VAD (we manually commit; server VAD is dead
       inference in PTT mode).
    3. Drop the ``"instructions"`` field from the ``response.create``
       payload (PR #2 review follow-up — already set in session.update,
       duplicating it costs tokenisation).
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        stt_config: STTConfig | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._stt_config = stt_config if stt_config is not None else DEFAULT_STT_CONFIG
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
                    # Counts only, no content. Stays in for the pilot so
                    # the cost logger has a paper trail per session.
                    logger.info("realtime.usage %s", usage)
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


def _extract_usage(event: dict[str, object]) -> CostUsage | None:
    """Parse the ``response.done.usage`` block into :class:`CostUsage`.

    Shape was verified 2026-05-22 against ``gpt-realtime`` GA. All
    sub-fields default to 0 when absent so newer responses with extra
    keys (e.g. image-related counts on a future modality) won't crash
    the pipeline.
    """
    response = event.get("response")
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None

    in_details = usage.get("input_token_details")
    in_details = in_details if isinstance(in_details, dict) else {}
    out_details = usage.get("output_token_details")
    out_details = out_details if isinstance(out_details, dict) else {}
    cached_details = in_details.get("cached_tokens_details")
    cached_details = cached_details if isinstance(cached_details, dict) else {}

    return CostUsage(
        audio_input_tokens=_int_or_zero(in_details.get("audio_tokens")),
        text_input_tokens=_int_or_zero(in_details.get("text_tokens")),
        cached_audio_input_tokens=_int_or_zero(cached_details.get("audio_tokens")),
        cached_text_input_tokens=_int_or_zero(cached_details.get("text_tokens")),
        text_output_tokens=_int_or_zero(out_details.get("text_tokens")),
        audio_output_tokens=_int_or_zero(out_details.get("audio_tokens")),
        total_tokens=_int_or_zero(usage.get("total_tokens")),
    )


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0
