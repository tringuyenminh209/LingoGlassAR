from __future__ import annotations

import pytest
from openai import OpenAIError

from app.services import text_translator
from app.services.cost_logger import CostUsage
from app.services.text_translator import ChatTranslator
from app.services.translator import TranslatorError


class _FakeDetails:
    def __init__(self, cached_tokens: int) -> None:
        self.cached_tokens = cached_tokens


class _FakeUsage:
    def __init__(
        self, prompt: int, completion: int, total: int, *, cached: int | None = None
    ) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total
        self.prompt_tokens_details = (
            _FakeDetails(cached) if cached is not None else None
        )


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str | None, usage: object) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, response: object, error: Exception | None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def _install(
    monkeypatch,
    *,
    response: object = None,
    error: Exception | None = None,
):
    """Patch ``text_translator.AsyncOpenAI`` with a fake client and return the
    list of constructed client instances plus the shared completions stub.
    """
    instances: list[object] = []
    completions = _FakeCompletions(response, error)

    class _FakeChat:
        def __init__(self) -> None:
            self.completions = completions

    class _FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.closed = False
            self.chat = _FakeChat()
            instances.append(self)

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(text_translator, "AsyncOpenAI", _FakeClient)
    return instances, completions


@pytest.mark.asyncio
async def test_translate_maps_usage_and_returns_text(monkeypatch) -> None:
    instances, completions = _install(
        monkeypatch,
        response=_FakeResponse("Xin chao", _FakeUsage(12, 7, 19)),
    )

    result = await ChatTranslator(api_key="k", model="gpt-4o-mini").translate("source")

    assert result.translated_text == "Xin chao"
    assert result.usage == CostUsage(
        audio_input_tokens=0,
        text_input_tokens=12,
        cached_audio_input_tokens=0,
        cached_text_input_tokens=0,
        text_output_tokens=7,
        audio_output_tokens=0,
        total_tokens=19,
    )
    # The configured model is forwarded to chat completions.
    assert completions.calls[0]["model"] == "gpt-4o-mini"
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_translate_none_content_returns_empty_text(monkeypatch) -> None:
    _install(monkeypatch, response=_FakeResponse(None, _FakeUsage(5, 0, 5)))

    result = await ChatTranslator(api_key="k", model="m").translate("source")

    assert result.translated_text == ""


@pytest.mark.asyncio
async def test_translate_missing_usage_returns_none_usage(monkeypatch) -> None:
    _install(monkeypatch, response=_FakeResponse("y", None))

    result = await ChatTranslator(api_key="k", model="m").translate("source")

    assert result.usage is None


@pytest.mark.asyncio
async def test_translate_maps_cached_prompt_tokens(monkeypatch) -> None:
    _install(
        monkeypatch,
        response=_FakeResponse("z", _FakeUsage(12, 7, 19, cached=3)),
    )

    result = await ChatTranslator(api_key="k", model="m").translate("source")

    assert result.usage is not None
    assert result.usage.text_input_tokens == 12
    assert result.usage.cached_text_input_tokens == 3


@pytest.mark.asyncio
async def test_translate_wraps_openai_error(monkeypatch) -> None:
    _install(monkeypatch, error=OpenAIError("upstream boom"))

    with pytest.raises(TranslatorError):
        await ChatTranslator(api_key="k", model="m").translate("source")


@pytest.mark.asyncio
async def test_translate_wraps_unexpected_error(monkeypatch) -> None:
    _install(monkeypatch, error=ValueError("weird"))

    with pytest.raises(TranslatorError):
        await ChatTranslator(api_key="k", model="m").translate("source")


@pytest.mark.asyncio
async def test_translate_closes_client_on_error(monkeypatch) -> None:
    instances, _ = _install(monkeypatch, error=OpenAIError("boom"))

    with pytest.raises(TranslatorError):
        await ChatTranslator(api_key="k", model="m").translate("source")

    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_translate_error_message_excludes_source_text(monkeypatch) -> None:
    secret = "PRIVATE_SOURCE_LINE_42"
    _install(monkeypatch, error=OpenAIError(f"rejected input: {secret}"))

    with pytest.raises(TranslatorError) as exc_info:
        await ChatTranslator(api_key="k", model="m").translate(secret)

    # Privacy: the surfaced message is the exception type only, never the text.
    assert secret not in str(exc_info.value)
