from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import sessions
from app.core.redis import get_redis
from app.main import create_app
from app.services.translator import TextDelta


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.expires: dict[str, int] = {}
        self.hset_calls: list[tuple[str, dict[str, str]]] = []
        self.expire_calls: list[tuple[str, int]] = []
        self.hgetall_calls: list[str] = []

    async def hset(self, name: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(name, {}).update(mapping)
        self.hset_calls.append((name, mapping))
        return len(mapping)

    async def expire(self, name: str, time: int) -> bool:
        self.expires[name] = time
        self.expire_calls.append((name, time))
        return True

    async def hgetall(self, name: str) -> dict[str, str]:
        self.hgetall_calls.append(name)
        return self.hashes.get(name, {})


class FakeTranslator:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def __aenter__(self) -> "FakeTranslator":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def translate_stream(
        self,
        audio_frames: AsyncIterator[bytes],
    ) -> AsyncIterator[TextDelta]:
        self.audio = [frame async for frame in audio_frames]
        yield TextDelta("Xin ")
        yield TextDelta("chao")
        yield TextDelta("", final=True)


def make_client(fake_redis: FakeRedis) -> TestClient:
    app = create_app()

    async def override_get_redis() -> AsyncIterator[FakeRedis]:
        yield fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    return TestClient(app)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def session_start(device_id: str) -> dict[str, object]:
    return {
        "type": "session.start",
        "deviceId": device_id,
        "sourceLang": "ja",
        "targetLang": "vi",
        "retainText": False,
        "clientTs": now_iso(),
    }


def audio_chunk(session_id: str, seq: int, payload: bytes) -> dict[str, object]:
    return {
        "type": "audio.chunk",
        "sessionId": session_id,
        "seq": seq,
        "codec": "pcm16",
        "sampleRateHz": 16000,
        "dataBase64": base64.b64encode(payload).decode("ascii"),
        "clientTs": now_iso(),
    }


def audio_end(session_id: str, seq: int) -> dict[str, object]:
    return {
        "type": "audio.end",
        "sessionId": session_id,
        "seq": seq,
        "clientTs": now_iso(),
    }


def test_create_session_returns_201_and_stores_session() -> None:
    fake_redis = FakeRedis()
    with make_client(fake_redis) as client:
        response = client.post("/v1/sessions")

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    UUID(data["sessionId"])
    assert data["wsUrl"].startswith(("ws://", "wss://"))
    datetime.fromisoformat(data["expiresAt"])

    key = f"session:{data['sessionId']}"
    assert fake_redis.hashes[key]["status"] == "open"
    assert fake_redis.expires[key] == 3600


def test_ws_unknown_session_closes_with_4404_and_error_frame() -> None:
    fake_redis = FakeRedis()
    with make_client(fake_redis) as client:
        with client.websocket_connect(f"/v1/sessions/{uuid4()}/stream") as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "session_not_found"
            try:
                ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code == 4404


def test_ws_happy_path_relays_translation(monkeypatch) -> None:
    fake_redis = FakeRedis()
    session_id = uuid4()
    fake_redis.hashes[f"session:{session_id}"] = {"status": "open"}
    monkeypatch.setattr(sessions, "Translator", FakeTranslator)

    with make_client(fake_redis) as client:
        with client.websocket_connect(f"/v1/sessions/{session_id}/stream") as ws:
            ws.send_json(session_start(str(uuid4())))
            opened = ws.receive_json()
            assert opened["type"] == "session.opened"

            ws.send_json(audio_chunk(str(session_id), 0, b"a" * 16))
            ws.send_json(audio_chunk(str(session_id), 1, b"b" * 16))
            ws.send_json(audio_end(str(session_id), 2))

            first = ws.receive_json()
            second = ws.receive_json()
            final = ws.receive_json()

    assert first["type"] == "translation.partial"
    assert first["text"] == "Xin "
    assert second["type"] == "translation.partial"
    assert second["text"] == "chao"
    assert final["type"] == "translation.final"
    assert final["translatedText"] == "Xin chao"


def test_ws_invalid_frame_returns_error_and_stays_open(monkeypatch) -> None:
    fake_redis = FakeRedis()
    session_id = uuid4()
    fake_redis.hashes[f"session:{session_id}"] = {"status": "open"}
    monkeypatch.setattr(sessions, "Translator", FakeTranslator)

    with make_client(fake_redis) as client:
        with client.websocket_connect(f"/v1/sessions/{session_id}/stream") as ws:
            ws.send_json({"type": "audio.chunk"})
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "invalid_event"
            assert error["retryable"] is True

            ws.send_json(session_start(str(uuid4())))
            opened = ws.receive_json()
            assert opened["type"] == "session.opened"
