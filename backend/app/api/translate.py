"""Translate-only REST path for the S3 on-device OCR flow.

The speech path (`/v1/sessions/.../stream`) streams audio through STT then
translate. OCR is different: the phone recognises the Japanese text on-device
(ML Kit) and only the recognised **text** crosses the wire — never image bytes.
So OCR needs a one-shot text->text translate, which this endpoint provides.

Design (S3 Day 2 locked REST; transport revised S3 Day 6 - see
docs/codex/S3_TASKS.md + docs/reports/S3_ocr_*.md):
- REST, not a new WS message type. OCR has the full text up front, so a
  one-shot request/response fits and keeps OCR fully isolated from the
  latency-gated speech WS state machine (zero regression risk).
- Translates via `ChatTranslator` (chat completions, one stateless HTTP
  request) rather than the Realtime `Translator`. Day 2 reused the Realtime
  session to keep one prompt source, but the Day 6 device bench showed opening
  a Realtime WS per capture cost ~4 s of handshake and blew the OCR latency
  gate. The JP<->VN prompt stays single-sourced via `SYSTEM_INSTRUCTIONS`,
  which `ChatTranslator` imports from the same module.
- Privacy: the request `text` (OCR'd source) and the response `translatedText`
  are NEVER logged or persisted. Counts/durations only, same as the audio path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from starlette.responses import JSONResponse

from app.api.sessions import ApiError, ApiFail, get_cost_logger
from app.core.config import Settings, get_settings
from app.core.redis import get_redis
from app.services.cost_logger import CostLogger, DailyCapExceeded, enforce_daily_cap
from app.services.text_translator import ChatTranslator
from app.services.translator import TranslatorError

router = APIRouter()

TRANSLATE_TEXT_MAX_LEN = 2000

# JP<->VN only, mirroring the audio path. The Realtime prompt auto-detects
# direction; sourceLang/targetLang are validated for contract clarity and to
# reject unsupported language pairs early.
TranslateLang = Literal["ja", "vi"]


class TranslateRequest(BaseModel):
    device_id: UUID | None = Field(default=None, alias="deviceId")
    source_lang: TranslateLang = Field(alias="sourceLang")
    target_lang: TranslateLang = Field(alias="targetLang")
    text: str = Field(min_length=1, max_length=TRANSLATE_TEXT_MAX_LEN)


class TranslateData(BaseModel):
    translated_text: str = Field(alias="translatedText")
    duration_ms: int = Field(alias="durationMs")


class TranslateResponse(BaseModel):
    success: Literal[True]
    data: TranslateData


def _utc_now() -> datetime:
    return datetime.now(UTC)


@router.post(
    "/v1/translate",
    status_code=200,
    response_model=TranslateResponse,
    responses={429: {"model": ApiFail}, 502: {"model": ApiFail}},
)
async def translate_text(
    redis: Annotated[Redis, Depends(get_redis)],
    cost_logger: Annotated[CostLogger, Depends(get_cost_logger)],
    settings: Annotated[Settings, Depends(get_settings)],
    payload: Annotated[TranslateRequest, Body()],
) -> TranslateResponse | JSONResponse:
    try:
        await enforce_daily_cap(cost_logger, cap_usd=settings.daily_usd_cap)
    except DailyCapExceeded as exc:
        return JSONResponse(
            status_code=429,
            content=ApiFail(
                success=False,
                error=ApiError(code="daily_cap_exceeded", message=str(exc)),
            ).model_dump(),
        )

    started_at = _utc_now()
    translator = ChatTranslator(
        api_key=settings.openai_api_key,
        model=settings.translate_model,
    )
    try:
        result = await translator.translate(payload.text)
    except TranslatorError as exc:
        return JSONResponse(
            status_code=502,
            content=ApiFail(
                success=False,
                error=ApiError(code="translator_error", message=str(exc)),
            ).model_dump(),
        )

    duration_ms = int((_utc_now() - started_at).total_seconds() * 1000)
    if result.usage is not None:
        # No session for a one-shot translate; key the cost record by a fresh
        # request id so it still rolls up into the 24h daily aggregate.
        await cost_logger.record(uuid4(), result.usage)

    return TranslateResponse(
        success=True,
        data=TranslateData(
            translatedText=result.translated_text,
            durationMs=duration_ms,
        ),
    )
