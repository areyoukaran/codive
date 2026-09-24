import asyncio
import math

from app.services.embeddings import DIM, LocalHashEmbedding, cosine_similarity


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_embedding_has_correct_dimension():
    vec = LocalHashEmbedding._embed_one("token rotation and refresh")
    assert len(vec) == DIM


def test_embedding_is_deterministic():
    text = "the rotation race in app/auth/tokens.py"
    a = LocalHashEmbedding._embed_one(text)
    b = LocalHashEmbedding._embed_one(text)
    assert a == b


def test_embedding_is_normalized():
    vec = LocalHashEmbedding._embed_one("some reasonably long piece of text about pgvector indexing")
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-9 or norm == 0.0


def test_empty_text_is_zero_vector():
    vec = LocalHashEmbedding._embed_one("")
    assert all(v == 0.0 for v in vec)


def test_similar_texts_score_higher_than_unrelated():
    a = LocalHashEmbedding._embed_one("token rotation refresh family reuse detection auth")
    b = LocalHashEmbedding._embed_one("refresh token rotation and family reuse in the auth service")
    c = LocalHashEmbedding._embed_one("terraform rds elasticache staging production infra")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_embed_batch_matches_single():
    provider = LocalHashEmbedding()
    texts = ["first chunk of readme text", "second chunk about installation"]
    batch = _run(provider.embed(texts))
    assert len(batch) == 2
    assert batch[0] == LocalHashEmbedding._embed_one(texts[0])
