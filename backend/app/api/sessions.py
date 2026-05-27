from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, WebSocket, WebSocketDisconnect
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from starlette.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.redis import get_redis
from app.services.cost_logger import (
    CostLogger,
    DailyCapExceeded,
    enforce_daily_cap,
)
from app.services.translator import Translator, TranslatorError

logger = logging.getLogger(__name__)

router = APIRouter()

SESSION_TTL_SECONDS = 3600
UNKNOWN_SESSION_CLOSE_CODE = 4404
TRANSLATOR_ERROR_CLOSE_CODE = 1011
_SENTINEL = object()


class SessionCreateRequest(BaseModel):
    device_id: UUID | None = Field(default=None, alias="deviceId")


class SessionCreateData(BaseModel):
    session_id: UUID = Field(alias="sessionId")
    ws_url: str = Field(alias="wsUrl")
    expires_at: datetime = Field(alias="expiresAt")


class SessionCreateResponse(BaseModel):
    success: Literal[True]
    data: SessionCreateData


class ApiError(BaseModel):
    code: str
    message: str


class ApiFail(BaseModel):
    success: Literal[False]
    error: ApiError


def get_cost_logger(
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CostLogger:
    return CostLogger(
        redis,
        usd_per_m_audio_input=settings.usd_per_m_audio_input,
        usd_per_m_text_input=settings.usd_per_m_text_input,
        usd_per_m_audio_cached_input=settings.usd_per_m_audio_cached_input,
        usd_per_m_text_cached_input=settings.usd_per_m_text_cached_input,
        usd_per_m_text_output=settings.usd_per_m_text_output,
        usd_per_m_audio_output=settings.usd_per_m_audio_output,
        daily_usd_cap=settings.daily_usd_cap,
        session_ttl_seconds=SESSION_TTL_SECONDS,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _ws_url(session_id: UUID) -> str:
    settings = get_settings()
    # `PUBLIC_BASE_URL` is the deployment-facing WS origin. Relying on
    # request.url_for inside Cloudflare/proxy setups would need forwarded
    # header handling, so we keep the public origin explicit and env-driven.
    return f"{settings.public_base_url.rstrip('/')}/v1/sessions/{session_id}/stream"


@router.post(
    "/v1/sessions",
    status_code=201,
    response_model=SessionCreateResponse,
    responses={429: {"model": ApiFail}},
)
async def create_session(
    redis: Annotated[Redis, Depends(get_redis)],
    cost_logger: Annotated[CostLogger, Depends(get_cost_logger)],
    settings: Annotated[Settings, Depends(get_settings)],
    payload: Annotated[SessionCreateRequest | None, Body()] = None,
) -> SessionCreateResponse | JSONResponse:
    try:
        await enforce_daily_cap(cost_logger, cap_usd=settings.daily_usd_cap)
    except DailyCapExceeded as exc:
        return JSONResponse(
            status_code=429,
            content=ApiFail(
                success=False,
                error=ApiError(
                    code="daily_cap_exceeded",
                    message=str(exc),
                ),
            ).model_dump(),
        )

    session_id = uuid4()
    created_at = _utc_now()
    expires_at = created_at + timedelta(seconds=SESSION_TTL_SECONDS)
    fields = {
        "created_at": created_at.isoformat(),
        "status": "open",
    }
    if payload and payload.device_id:
        fields["device_id"] = str(payload.device_id)

    key = f"session:{session_id}"
    await redis.hset(key, mapping=fields)
    await redis.expire(key, SESSION_TTL_SECONDS)

    return SessionCreateResponse(
        success=True,
        data=SessionCreateData(
            sessionId=session_id,
            wsUrl=_ws_url(session_id),
            expiresAt=expires_at,
        ),
    )


@router.websocket("/v1/sessions/{session_id}/stream")
async def session_stream(
    websocket: WebSocket,
    session_id: UUID,
    redis: Annotated[Redis, Depends(get_redis)],
    cost_logger: Annotated[CostLogger, Depends(get_cost_logger)],
) -> None:
    await websocket.accept()
    session_key = f"session:{session_id}"
    if not await redis.hgetall(session_key):
        await _send_error(
            websocket,
            code="session_not_found",
            message="session not found",
            retryable=False,
            session_id=session_id,
        )
        await websocket.close(code=UNKNOWN_SESSION_CLOSE_CODE)
        return

    queue: asyncio.Queue[bytes | object] = asyncio.Queue()
    translator: Translator | None = None
    opened_at: datetime | None = None
    started = False
    translated_parts: list[str] = []
    source_text: str | None = None

    try:
        while True:
            try:
                event = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            try:
                _validate_ws_event(event)
            except ValidationError as ve:
                # Log validation failures so we can debug malformed client
                # events without trusting the client to report them. Type +
                # JSON-pointer path only; no payload values.
                logger.warning(
                    "ws.invalid_event session=%s type=%s path=%s reason=%s",
                    session_id,
                    event.get("type") if isinstance(event, dict) else None,
                    "/".join(str(p) for p in ve.absolute_path) or "<root>",
                    ve.validator,
                )
                await _send_error(
                    websocket,
                    code="invalid_event",
                    message="invalid event",
                    retryable=True,
                    session_id=session_id,
                )
                continue

            event_type = event.get("type")

            if event_type == "metrics":
                continue

            if event_type != "session.start" and not started:
                await _send_error(
                    websocket,
                    code="invalid_event",
                    message="session.start must be the first non-metrics frame",
                    retryable=True,
                    session_id=session_id,
                )
                continue

            if event_type == "session.start":
                if started:
                    await _send_error(
                        websocket,
                        code="invalid_event",
                        message="session already opened",
                        retryable=True,
                        session_id=session_id,
                    )
                    continue
                translator = Translator(api_key=get_settings().openai_api_key)
                try:
                    await translator.__aenter__()
                except TranslatorError as exc:
                    await _send_error(
                        websocket,
                        code="translator_error",
                        message=str(exc),
                        retryable=True,
                        session_id=session_id,
                    )
                    await websocket.close(code=TRANSLATOR_ERROR_CLOSE_CODE)
                    return
                started = True
                opened_at = _utc_now()
                await websocket.send_json(
                    {
                        "type": "session.opened",
                        "sessionId": str(session_id),
                        "serverTs": opened_at.isoformat(),
                    }
                )
            elif event_type == "audio.chunk":
                try:
                    chunk = base64.b64decode(event["dataBase64"], validate=True)
                except Exception:
                    await _send_error(
                        websocket,
                        code="invalid_event",
                        message="invalid base64 audio payload",
                        retryable=True,
                        session_id=session_id,
                    )
                    continue
                await queue.put(chunk)
            elif event_type == "audio.end":
                await queue.put(_SENTINEL)
                if translator is None or opened_at is None:
                    await _send_error(
                        websocket,
                        code="invalid_event",
                        message="translator is not open",
                        retryable=True,
                        session_id=session_id,
                    )
                    continue
                try:
                    async for delta in translator.translate_stream(
                        _audio_iterator(queue)
                    ):
                        if delta.source_text is not None:
                            source_text = delta.source_text
                        if delta.text and not delta.final:
                            translated_parts.append(delta.text)
                            await websocket.send_json(
                                {
                                    "type": "translation.partial",
                                    "sessionId": str(session_id),
                                    "text": delta.text,
                                    "serverTs": _iso_now(),
                                }
                            )
                        if delta.final:
                            server_ts = _utc_now()
                            payload: dict[str, Any] = {
                                "type": "translation.final",
                                "sessionId": str(session_id),
                                "translatedText": "".join(translated_parts),
                                "durationMs": int(
                                    (server_ts - opened_at).total_seconds() * 1000
                                ),
                                "serverTs": server_ts.isoformat(),
                            }
                            if source_text is not None:
                                payload["sourceText"] = source_text
                            await websocket.send_json(payload)
                            if delta.usage is not None:
                                await cost_logger.record(session_id, delta.usage)
                            break
                except TranslatorError as exc:
                    await _send_error(
                        websocket,
                        code="translator_error",
                        message=str(exc),
                        retryable=True,
                        session_id=session_id,
                    )
                    await websocket.close(code=TRANSLATOR_ERROR_CLOSE_CODE)
                    return
    finally:
        if translator is not None:
            await translator.__aexit__(None, None, None)


async def _audio_iterator(
    queue: asyncio.Queue[bytes | object],
) -> AsyncIterator[bytes]:
    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        yield item  # type: ignore[misc]


async def _send_error(
    websocket: WebSocket,
    *,
    code: str,
    message: str,
    retryable: bool,
    session_id: UUID | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": "error",
        "code": code,
        "message": message,
        "retryable": retryable,
        "serverTs": _iso_now(),
    }
    if session_id is not None:
        payload["sessionId"] = str(session_id)
    await websocket.send_json(payload)


def _validate_ws_event(event: Any) -> None:
    _WS_EVENT_VALIDATOR.validate(event)


def _load_ws_schema() -> dict[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "api-contract"
        / "ws-events.schema.json"
    )
    if schema_path.exists():
        import json

        return json.loads(schema_path.read_text(encoding="utf-8"))
    return _WS_SCHEMA_FALLBACK


_WS_SCHEMA_FALLBACK: dict[str, Any] = {
    "oneOf": [
        {"$ref": "#/$defs/sessionStart"},
        {"$ref": "#/$defs/audioChunk"},
        {"$ref": "#/$defs/audioEnd"},
        {"$ref": "#/$defs/metrics"},
    ],
    "$defs": {
        "uuid": {"type": "string", "format": "uuid"},
        "isoTs": {"type": "string", "format": "date-time"},
        "lang": {"type": "string", "enum": ["ja", "en", "vi", "ko", "zh-CN"]},
        "sessionStart": {
            "type": "object",
            "required": [
                "type",
                "deviceId",
                "sourceLang",
                "targetLang",
                "retainText",
                "clientTs",
            ],
            "properties": {
                "type": {"const": "session.start"},
                "deviceId": {"$ref": "#/$defs/uuid"},
                "sourceLang": {"$ref": "#/$defs/lang"},
                "targetLang": {"$ref": "#/$defs/lang"},
                "retainText": {"type": "boolean"},
                "clientTs": {"$ref": "#/$defs/isoTs"},
            },
            "additionalProperties": False,
        },
        "audioChunk": {
            "type": "object",
            "required": [
                "type",
                "sessionId",
                "seq",
                "codec",
                "sampleRateHz",
                "dataBase64",
                "clientTs",
            ],
            "properties": {
                "type": {"const": "audio.chunk"},
                "sessionId": {"$ref": "#/$defs/uuid"},
                "seq": {"type": "integer", "minimum": 0},
                "codec": {"const": "pcm16"},
                "sampleRateHz": {"const": 24000},
                "dataBase64": {"type": "string", "contentEncoding": "base64"},
                "clientTs": {"$ref": "#/$defs/isoTs"},
            },
            "additionalProperties": False,
        },
        "audioEnd": {
            "type": "object",
            "required": ["type", "sessionId", "seq", "clientTs"],
            "properties": {
                "type": {"const": "audio.end"},
                "sessionId": {"$ref": "#/$defs/uuid"},
                "seq": {"type": "integer", "minimum": 0},
                "clientTs": {"$ref": "#/$defs/isoTs"},
            },
            "additionalProperties": False,
        },
        "metrics": {
            "type": "object",
            "required": ["type", "sessionId", "name", "valueMs", "clientTs"],
            "properties": {
                "type": {"const": "metrics"},
                "sessionId": {"$ref": "#/$defs/uuid"},
                "name": {"type": "string"},
                "valueMs": {"type": "integer", "minimum": 0},
                "clientTs": {"$ref": "#/$defs/isoTs"},
            },
            "additionalProperties": False,
        },
    },
}

_WS_EVENT_VALIDATOR = Draft202012Validator(_load_ws_schema())
