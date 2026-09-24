"""
Every AI-facing feature (PR summaries, issue summaries, the daily brief
line, and /ask) goes through `LLMProvider.complete()`. Three providers:

  - GroqProvider: Groq's OpenAI-compatible endpoint, free tier, no card.
    Fast - usually the right default once a key exists.
  - GeminiProvider: Google AI Studio free tier, no card. Used if only
    GEMINI_API_KEY is set, or as an explicit choice.
  - TemplateProvider: zero dependencies, zero network, zero cost. Composes
    a plain-English answer directly from the structured facts it's given,
    with no model in the loop at all. This is what runs with no key
    configured - the feature stays real (grounded in real synced data),
    just not phrased by a model.

All three implement the same `complete(system, user, max_tokens)` shape so
routers never know which one answered.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from app.core.config import get_settings

# httpx is imported lazily inside each provider's complete() rather than at
# module level, so TemplateProvider and get_llm_provider() - which need no
# third-party package at all - stay importable and unit-testable without
# httpx installed. Production always has httpx (requirements.txt).

log = logging.getLogger("codive.llm")


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, system: str, user: str, *, max_tokens: int = 500) -> str: ...


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self._model = model

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 500
    ) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=45.0) as c:
            resp = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )

        if resp.status_code == 429:
            raise LLMError(
                "Groq rate limit hit - try again shortly."
            )

        if resp.status_code >= 400:
            try:
                error = resp.json().get("error", {})
                message = error.get("message", resp.text)
            except Exception:
                message = resp.text

            raise LLMError(
                f"Groq API error ({resp.status_code}): {message[:500]}"
            )

        try:
            data = resp.json()
            content = data["choices"][0]["message"].get("content")
            if not isinstance(content, str) or not content.strip():
                raise LLMError(
                    f"Groq returned an empty answer: {resp.text[:500]}"
                )
            return content.strip()
        except LLMError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError(
                f"Unexpected Groq response: {resp.text[:500]}"
            ) from exc


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self._model = model

    async def complete(self, system: str, user: str, *, max_tokens: int = 500) -> str:
        import httpx  # lazy - see note at top of file

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        async with httpx.AsyncClient(timeout=45.0) as c:
            resp = await c.post(
                url,
                params={"key": self._key},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
                },
            )
            if resp.status_code == 429:
                raise LLMError("Gemini rate limit hit - try again shortly")
            if resp.status_code >= 400:
                try:
                    error = resp.json().get("error", {})
                    message = error.get("message", resp.text)
                except Exception:
                    message = resp.text
                raise LLMError(
                    f"Gemini API error ({resp.status_code}): {message[:500]}"
                )
            data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict)
            ).strip()
            if not text:
                raise LLMError(
                    f"Gemini returned an empty answer: {json.dumps(data)[:500]}"
                )
            return text
        except LLMError:
            raise
        except (KeyError, IndexError, TypeError):
            raise LLMError(
                f"Unexpected Gemini response shape: {json.dumps(data)[:500]}"
            )


class TemplateProvider(LLMProvider):
    """No model. Used with no LLM key configured. Callers pass the same
    system/user prompt text as the other providers, so this doesn't try to
    parse it - it just returns an honest, unglamorous placeholder that
    tells the reader why they're seeing it. Routers that want a grounded
    non-AI answer (e.g. the templated brief line) build that text
    themselves and skip calling this at all; this exists so a naive
    caller never gets a silent crash."""
    name = "template"

    async def complete(self, system: str, user: str, *, max_tokens: int = 500) -> str:
        return (
            "AI summaries need a free GROQ_API_KEY or GEMINI_API_KEY configured on the backend. "
            "Everything else here - repositories, commits, pull requests, issues - is real synced data."
        )


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    choice = settings.llm_provider
    if choice == "groq" and settings.groq_api_key:
        return GroqProvider(settings.groq_api_key, settings.groq_model)
    if choice == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if choice == "none":
        return TemplateProvider()
    # auto: prefer Groq (faster), then Gemini, then the honest template
    if settings.groq_api_key:
        return GroqProvider(settings.groq_api_key, settings.groq_model)
    if settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return TemplateProvider()


ASK_SYSTEM_PROMPT = """You are Codive, a repository intelligence assistant. \
Answer only from the repository state you are given as JSON. If the state does not \
contain the answer, say so plainly and name what you would need - never guess.

Be brief: 2-4 sentences or up to 4 short lines. Plain prose, no markdown headings, no bold.

Cite every factual claim with an inline marker right after the claim, using only \
identifiers present in the state: [pr:123] for a pull request, [issue:45] for an issue, \
[commit:abc1234] for a commit, [file:path/to/file.py:88] for a file, [repo:owner/name] \
for a repository. Do not add a separate sources list - the inline markers are the citation."""
