"""
Embedding providers for Codive.

Providers:
- LocalHashEmbedding: deterministic local fallback.
- GeminiEmbedding: Google Gemini Embedding 2.

Gemini Embedding 2 supports configurable output dimensions.
Codive uses 384 dimensions so it remains compatible with the
existing pgvector schema.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import get_settings


DIM = 384

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalHashEmbedding(EmbeddingProvider):
    name = "local"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vec = [0.0] * DIM

        tokens = _TOKEN_RE.findall(text.lower())

        if not tokens:
            return vec

        for token in tokens:
            h = int(
                hashlib.blake2b(
                    token.encode(),
                    digest_size=8,
                ).hexdigest(),
                16,
            )

            idx = h % DIM
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec)) or 1.0

        return [v / norm for v in vec]


class GeminiEmbedding(EmbeddingProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-2",
    ):
        self._key = api_key
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        if not texts:
            return []

        url = (
            "https://generativelanguage.googleapis.com"
            f"/v1beta/models/{self._model}:batchEmbedContents"
        )

        requests = [
            {
                "model": f"models/{self._model}",
                "content": {
                    "parts": [
                        {
                            "text": text[:8000],
                        }
                    ]
                },
                "outputDimensionality": DIM,
            }
            for text in texts
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                params={"key": self._key},
                json={"requests": requests},
            )

        if response.status_code != 200:
            raise RuntimeError(
                "Gemini embedding request failed "
                f"({response.status_code}): {response.text[:1000]}"
            )

        data = response.json()

        embeddings = data.get("embeddings")

        if not embeddings:
            raise RuntimeError(
                f"Gemini returned no embeddings: {data}"
            )

        vectors = [item["values"] for item in embeddings]

        if len(vectors) != len(texts):
            raise RuntimeError(
                "Gemini returned an unexpected number of embeddings: "
                f"expected {len(texts)}, got {len(vectors)}"
            )

        for index, vector in enumerate(vectors):
            if len(vector) != DIM:
                raise RuntimeError(
                    f"Gemini returned dimension {len(vector)} "
                    f"for item {index}; expected {DIM}"
                )

        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()

    choice = settings.embedding_provider.lower()

    if choice == "local":
        return LocalHashEmbedding()

    if choice == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=gemini but GEMINI_API_KEY is missing"
            )

        return GeminiEmbedding(
            settings.gemini_api_key,
            settings.embedding_model,
        )

    # auto
    if settings.gemini_api_key:
        return GeminiEmbedding(
            settings.gemini_api_key,
            settings.embedding_model,
        )

    return LocalHashEmbedding()


def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:
    dot = sum(x * y for x, y in zip(a, b))

    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0

    return dot / (na * nb)