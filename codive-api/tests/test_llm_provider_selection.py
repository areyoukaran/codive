import asyncio
import os

from app.core.config import get_settings
from app.services.llm import GeminiProvider, GroqProvider, TemplateProvider, get_llm_provider


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _reset_env(**kwargs):
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER"):
        os.environ.pop(key, None)
    for k, v in kwargs.items():
        os.environ[k] = v
    get_settings.cache_clear()


def test_no_keys_returns_template_provider():
    _reset_env()
    provider = get_llm_provider()
    assert isinstance(provider, TemplateProvider)
    assert provider.name == "template"


def test_groq_key_alone_selects_groq():
    _reset_env(GROQ_API_KEY="fake-groq-key")
    provider = get_llm_provider()
    assert isinstance(provider, GroqProvider)


def test_gemini_key_alone_selects_gemini():
    _reset_env(GEMINI_API_KEY="fake-gemini-key")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_both_keys_prefers_groq_in_auto_mode():
    _reset_env(GROQ_API_KEY="fake-groq-key", GEMINI_API_KEY="fake-gemini-key")
    provider = get_llm_provider()
    assert isinstance(provider, GroqProvider)


def test_explicit_none_forces_template_even_with_keys():
    _reset_env(GROQ_API_KEY="fake-groq-key", LLM_PROVIDER="none")
    provider = get_llm_provider()
    assert isinstance(provider, TemplateProvider)
    _reset_env()  # leave environment clean for later tests in the same process


def test_template_provider_never_raises_and_stays_honest():
    _reset_env()
    provider = TemplateProvider()
    result = _run(provider.complete("system prompt", "user question"))
    assert "GROQ_API_KEY" in result or "GEMINI_API_KEY" in result
