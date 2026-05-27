import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

import pytest

from app.services.cost_logger import CostUsage
from app.services.translator import (
    STTConfig,
    TextDelta,
    TextResult,
    Translator,
    TranslatorError,
)


class FakeWebSocket:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self.events = events
        self.sent: list[dict[str, object]] = []
        self.closed = False

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> "FakeWebSocket":
        return self

    async def __anext__(self) -> str:
        if not self.events:
            raise StopAsyncIteration
        return json.dumps(self.events.pop(0))


async def audio_chunks() -> AsyncIterator[bytes]:
    for value in (b"a" * 16, b"b" * 16, b"c" * 16):
        yield value


@pytest.mark.asyncio
async def test_translate_stream_emits_text_deltas_in_order(monkeypatch) -> None:
    fake_ws = FakeWebSocket(
        [
            {"type": "response.text.delta", "delta": "Xin "},
            {"type": "response.text.delta", "delta": "chao"},
            {"type": "response.text.done"},
        ]
    )

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        results = [delta async for delta in translator.translate_stream(audio_chunks())]

    assert results == [
        TextDelta(text="Xin "),
        TextDelta(text="chao"),
        TextDelta(text="", final=True),
    ]
    sent_types = [event["type"] for event in fake_ws.sent]
    assert sent_types == [
        "session.update",
        "input_audio_buffer.append",
        "input_audio_buffer.append",
        "input_audio_buffer.append",
        "input_audio_buffer.commit",
        "response.create",
    ]
    assert fake_ws.closed is True


@pytest.mark.asyncio
async def test_session_update_uses_stt_config_defaults(monkeypatch) -> None:
    fake_ws = FakeWebSocket([])

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="x"):
        pass

    session_update = fake_ws.sent[0]
    session = session_update["session"]
    audio_input = session["audio"]["input"]

    assert session_update["type"] == "session.update"
    assert audio_input["transcription"] == {"model": "whisper-1"}
    assert "delay" not in audio_input["transcription"]
    assert "turn_detection" in audio_input
    assert audio_input["turn_detection"] is None
    assert "turn_detection" not in session


@pytest.mark.asyncio
async def test_session_update_honours_custom_stt_config(monkeypatch) -> None:
    fake_ws = FakeWebSocket([])

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(
        api_key="x",
        stt_config=STTConfig(
            transcription_model="gpt-realtime-whisper",
            transcription_delay="low",
        ),
    ):
        pass

    session_update = fake_ws.sent[0]
    transcription = session_update["session"]["audio"]["input"]["transcription"]

    assert transcription == {"model": "gpt-realtime-whisper", "delay": "low"}


@pytest.mark.asyncio
async def test_response_create_omits_instructions(monkeypatch) -> None:
    fake_ws = FakeWebSocket([{"type": "response.text.done"}])

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="x") as translator:
        _ = [delta async for delta in translator.translate_stream(audio_chunks())]

    response_create = next(
        event for event in fake_ws.sent if event["type"] == "response.create"
    )
    response = response_create["response"]

    assert response["output_modalities"] == ["text"]
    assert "instructions" not in response


@pytest.mark.asyncio
async def test_translate_stream_yields_final_delta_on_text_done(monkeypatch) -> None:
    fake_ws = FakeWebSocket([{"type": "response.text.done"}])

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        results = [delta async for delta in translator.translate_stream(audio_chunks())]

    assert results == [TextDelta(text="", final=True)]


@pytest.mark.asyncio
async def test_translate_stream_raises_translator_error_on_error_event(
    monkeypatch,
) -> None:
    fake_ws = FakeWebSocket(
        [
            {
                "type": "error",
                "error": {"message": "bad audio frame"},
            }
        ]
    )

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        with pytest.raises(TranslatorError, match="bad audio frame"):
            _ = [delta async for delta in translator.translate_stream(audio_chunks())]


@pytest.mark.asyncio
async def test_translate_text_joins_deltas_and_parses_usage(monkeypatch) -> None:
    fake_ws = FakeWebSocket(
        [
            {"type": "response.output_text.delta", "delta": "Xin "},
            {"type": "response.output_text.delta", "delta": "chao"},
            {
                "type": "response.done",
                "response": {
                    "usage": {
                        "total_tokens": 19,
                        "input_token_details": {
                            "audio_tokens": 0,
                            "text_tokens": 12,
                            "cached_tokens_details": {
                                "audio_tokens": 0,
                                "text_tokens": 3,
                            },
                        },
                        "output_token_details": {
                            "audio_tokens": 0,
                            "text_tokens": 7,
                        },
                    }
                },
            },
        ]
    )

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        result = await translator.translate_text("source text")

    assert result == TextResult(
        translated_text="Xin chao",
        usage=CostUsage(
            audio_input_tokens=0,
            text_input_tokens=12,
            cached_audio_input_tokens=0,
            cached_text_input_tokens=3,
            text_output_tokens=7,
            audio_output_tokens=0,
            total_tokens=19,
        ),
    )
    assert [event["type"] for event in fake_ws.sent] == [
        "session.update",
        "conversation.item.create",
        "response.create",
    ]


@pytest.mark.asyncio
async def test_translate_text_returns_joined_text_without_response_done(
    monkeypatch,
) -> None:
    fake_ws = FakeWebSocket(
        [
            {"type": "response.output_text.delta", "delta": "Xin "},
            {"type": "response.output_text.delta", "delta": "chao"},
        ]
    )

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        result = await translator.translate_text("source text")

    assert result == TextResult(translated_text="Xin chao", usage=None)


@pytest.mark.asyncio
async def test_translate_text_raises_translator_error_on_error_event(
    monkeypatch,
) -> None:
    fake_ws = FakeWebSocket([{"type": "error", "error": {"message": "text rejected"}}])

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        with pytest.raises(TranslatorError, match="text rejected"):
            await translator.translate_text("source text")


@pytest.mark.asyncio
async def test_translate_text_requires_connection() -> None:
    translator = Translator(api_key="test-key")

    with pytest.raises(RuntimeError, match="not connected"):
        await translator.translate_text("source text")


@pytest.mark.asyncio
async def test_translate_text_rejects_call_while_audio_stream_active(
    monkeypatch,
) -> None:
    fake_ws = FakeWebSocket([])
    release_audio = asyncio.Event()

    async def fake_connect(*args, **kwargs) -> FakeWebSocket:
        return fake_ws

    async def blocked_audio() -> AsyncIterator[bytes]:
        await release_audio.wait()
        yield b"a" * 16

    monkeypatch.setattr("app.services.translator.websockets.connect", fake_connect)

    async with Translator(api_key="test-key") as translator:
        stream = translator.translate_stream(blocked_audio())
        pending_delta = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        try:
            with pytest.raises(RuntimeError, match="active stream"):
                await translator.translate_text("source text")
        finally:
            pending_delta.cancel()
            with suppress(asyncio.CancelledError):
                await pending_delta
            await stream.aclose()
