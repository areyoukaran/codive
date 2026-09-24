"""
Two embedding providers behind one interface, chosen so the search feature
works even with zero external accounts:

  - LocalHashEmbedding: a deterministic, dependency-free bag-of-words
    hashing vector. Not semantically strong, but it costs nothing, needs no
    API key, and runs inside the free web service's own memory — good
    enough for exact-ish and near-miss matching, which is what §12's
    "exact and semantic search" actually needs at MVP scope.
  - GeminiEmbedding: Google AI Studio's free-tier text-embedding endpoint,
    used automatically the moment GEMINI_API_KEY is set, no code change.

Both return a 384-dim vector so they're interchangeable in the same
pgvector column (see app/db/models.py:_EMBED_DIM).
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import get_settings

# httpx is imported lazily inside GeminiEmbedding.embed() rather than at
# module level, purely so LocalHashEmbedding and cosine_similarity — which
# have zero third-party dependencies — stay importable and unit-testable
# without httpx installed. Production always has httpx (requirements.txt).

DIM = 384
_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashEmbedding(EmbeddingProvider):
    name = "local"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vec = [0.0] * DIM
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec
        for tok in tokens:
            h = int(hashlib.blake2b(tok.encode(), digest_size=8).hexdigest(), 16)
            idx = h % DIM
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class GeminiEmbedding(EmbeddingProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        self._key = api_key
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx  # lazy — see note at top of file

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:batchEmbedContents"
        requests = [
            {"model": f"models/{self._model}", "content": {"parts": [{"text": t[:8000]}]}, "outputDimensionality": DIM}
            for t in texts
        ]
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(url, params={"key": self._key}, json={"requests": requests})
            resp.raise_for_status()
            data = resp.json()
        return [e["values"] for e in data["embeddings"]]


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    choice = settings.embedding_provider
    if choice == "local":
        return LocalHashEmbedding()
    if choice == "gemini" and settings.gemini_api_key:
        return GeminiEmbedding(settings.gemini_api_key)
    # auto
    if settings.gemini_api_key:
        return GeminiEmbedding(settings.gemini_api_key)
    return LocalHashEmbedding()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
