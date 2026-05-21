"""OpenAI Realtime translator service — interface contract (S1 Day 2).

Design decisions locked here (Codex implements against this, does not
rename or rewrite the public surface):

1. Streaming generator (`AsyncIterator[TextDelta]`) over callback. Aligns
   with the FastAPI WS bridge planned for S1 Day 3 and keeps the
   backpressure model simple — the consumer pulls.
2. One WS per `Translator` instance. The caller owns the lifecycle via
   the async context manager. Concurrent `translate_stream()` calls on
   the same instance are not supported (one utterance at a time).
3. `TextDelta` carries incremental chunks AND a `final` marker. Renderers
   can paint as they go and commit on `final=True`.
4. Source-language transcription text rides on a separate field
   (`source_text`) so the S1 Day 8 cost logger can attribute usage
   without the BLE renderer caring. Never log this value — privacy
   boundary from backend/CLAUDE.md.
5. OpenAI `error` events become `TranslatorError`. Do not swallow.

Codex: implementation details (which SDK call, framing strategy,
reconnect behaviour) are yours. Only the public API below is locked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator


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
        raise NotImplementedError("S1 Day 2 — Codex implements")

    async def __aenter__(self) -> "Translator":
        raise NotImplementedError

    async def __aexit__(self, exc_type, exc, tb) -> None:
        raise NotImplementedError

    async def connect(self) -> None:
        """Open the WebSocket and send the initial session configuration.

        Idempotent: calling on an already-connected instance is a no-op.
        """
        raise NotImplementedError

    async def close(self) -> None:
        """Close the WebSocket. Safe to call multiple times."""
        raise NotImplementedError

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
        raise NotImplementedError
        yield  # pragma: no cover  -- marks this as an async generator
