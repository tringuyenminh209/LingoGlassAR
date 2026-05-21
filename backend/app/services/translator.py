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
from dataclasses import dataclass
from types import TracebackType
from typing import AsyncIterator

import websockets


SYSTEM_INSTRUCTIONS = (
    "You are a JP<->VN translator. When you receive Japanese audio, "
    "output Vietnamese text only. When you receive Vietnamese audio, "
    "output Japanese text only. No commentary, no romanization."
)

DEFAULT_MODEL = "gpt-4o-realtime-preview"


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
    """

    text: str
    final: bool = False
    source_text: str | None = None


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
    Input frames are raw PCM16 mono at 16 kHz. Frame size is caller's
    choice; ~100 ms (3200 bytes) is recommended. Frames are forwarded
    to OpenAI as ``input_audio_buffer.append`` events.

    Session prompt
    --------------
    A fixed ``session.update`` with :data:`SYSTEM_INSTRUCTIONS` is sent
    on connect. ``input_audio_transcription`` must be enabled so we get
    the source-language text on :attr:`TextDelta.source_text`.
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
            self._ws = await websockets.connect(
                url,
                extra_headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "OpenAI-Beta": "realtime=v1",
                },
            )
            await self._send_json(
                {
                    "type": "session.update",
                    "session": {
                        "instructions": SYSTEM_INSTRUCTIONS,
                        "input_audio_format": "pcm16",
                        "input_audio_transcription": {"model": "whisper-1"},
                        "modalities": ["text"],
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
            await self._send_json(
                {
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"],
                        "instructions": SYSTEM_INSTRUCTIONS,
                    },
                }
            )

            async for raw_event in self._ws:
                event = _decode_event(raw_event)
                event_type = event.get("type")

                if event_type == "response.text.delta":
                    yield TextDelta(text=str(event.get("delta", "")))
                elif event_type == "response.text.done":
                    yield TextDelta(text="", final=True)
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
        except TranslatorError:
            raise
        except Exception as exc:
            raise TranslatorError("OpenAI Realtime WebSocket failed") from exc
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
