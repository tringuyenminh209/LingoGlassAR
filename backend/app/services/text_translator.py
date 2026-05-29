"""One-shot text translation for the S3 OCR path (chat completions).

S3 Day 6 device bench (docs/reports/S3_ocr_*.md) showed the original
``/v1/translate`` path - which opened a fresh OpenAI Realtime WebSocket per
request via ``Translator.connect()`` - spent ~4-4.6 s on the WS handshake alone
on every capture, blowing the OCR latency gate (p95 <= 1500 ms). The speech
path amortises that handshake across a whole utterance (the session is opened at
PTT press, concurrent with the user holding the button); OCR has no warm
session, so each capture paid the full setup cost.

A one-shot text->text translate is exactly what chat completions is for: a
single stateless HTTP request, no WebSocket upgrade. This module keeps the
JP<->VN prompt single-sourced by reusing :data:`SYSTEM_INSTRUCTIONS`, and reuses
:class:`TextResult` / :class:`TranslatorError` / :class:`CostUsage` so the
handler's error mapping (502) and cost logging are unchanged.

Privacy: the source text and the translation are NEVER logged or persisted -
counts/durations only, same boundary as the audio path. The wrapped error
message carries the exception type name only, never the source text, because the
handler surfaces ``str(exc)`` in the 502 response body.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI, OpenAIError

from app.services.cost_logger import CostUsage
from app.services.translator import SYSTEM_INSTRUCTIONS, TextResult, TranslatorError

logger = logging.getLogger(__name__)


class ChatTranslator:
    """Async one-shot JP<->VN translator over the OpenAI chat completions API.

    Unlike :class:`Translator` (a persistent Realtime WebSocket), each
    :meth:`translate` is a single stateless HTTP request, so there is no
    connect/close lifecycle for the caller to manage - the right shape for OCR,
    which holds the full recognised text up front and has nothing to stream.
    """

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def translate(self, text: str) -> TextResult:
        """Translate one block of text. Raises :class:`TranslatorError` on any
        failure so the handler maps it to a 502 the same way the audio path does.
        """
        client = AsyncOpenAI(api_key=self._api_key)
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": text},
                ],
            )
        except OpenAIError as exc:
            # Type name only - never the source text or the API error body.
            raise TranslatorError(
                f"OpenAI chat completions failed: {type(exc).__name__}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - surface everything as TranslatorError
            raise TranslatorError(
                f"chat translate failed: {type(exc).__name__}"
            ) from exc
        finally:
            await client.close()

        choices = getattr(response, "choices", None) or []
        translated = (choices[0].message.content or "") if choices else ""
        usage = _usage_from_response(response)
        # Counts only, no content - same paper trail as the audio path.
        logger.info("chat.usage %s", usage)
        return TextResult(translated, usage)


def _usage_from_response(response: object) -> CostUsage | None:
    """Map a chat completions ``usage`` block onto :class:`CostUsage`.

    Chat completions report ``prompt_tokens`` / ``completion_tokens`` /
    ``total_tokens`` (text only - no audio), plus an optional
    ``prompt_tokens_details.cached_tokens``. These map onto the text fields of
    :class:`CostUsage`; the audio fields stay 0. Note the daily-cost rates in
    config are the ``gpt-realtime`` text rates, so a cheaper chat model is
    over-estimated - that is intentionally conservative for the daily cap.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    cached = _int_or_zero(getattr(details, "cached_tokens", 0)) if details else 0
    return CostUsage(
        audio_input_tokens=0,
        text_input_tokens=_int_or_zero(getattr(usage, "prompt_tokens", 0)),
        cached_audio_input_tokens=0,
        cached_text_input_tokens=cached,
        text_output_tokens=_int_or_zero(getattr(usage, "completion_tokens", 0)),
        audio_output_tokens=0,
        total_tokens=_int_or_zero(getattr(usage, "total_tokens", 0)),
    )


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0
