"""The sentence-transformers adapter against a real model.

Every other test in the suite uses a fake encoder, so a sentence-transformers major
could remove a call this adapter makes and the suite would stay green. This file loads
a small real model (~70 MB, CPU) and checks the three things the adapter relies on:
the constructor, the embedding-dimension accessor, and ``encode(normalize_embeddings=True)``.
"""

from __future__ import annotations

import math

import pytest

from diploma_equivalence.infrastructure.adapters.embed import SentenceTransformersEmbedder

MODEL = "sentence-transformers/paraphrase-MiniLM-L3-v2"
DIMENSION = 384

pytestmark = pytest.mark.embed


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformersEmbedder:
    return SentenceTransformersEmbedder(model_name=MODEL, device="cpu")


def _dot(u: list[float], v: list[float]) -> float:
    return sum(x * y for x, y in zip(u, v, strict=True))


def test_dimension_comes_from_the_loaded_model(embedder: SentenceTransformersEmbedder) -> None:
    assert embedder.dimension == DIMENSION


def test_encode_returns_unit_length_float_lists(embedder: SentenceTransformersEmbedder) -> None:
    vectors = embedder.encode(["linear algebra", "medieval poetry"])

    assert [len(v) for v in vectors] == [DIMENSION, DIMENSION]
    assert all(isinstance(x, float) for x in vectors[0])
    for vector in vectors:
        assert math.isclose(math.sqrt(_dot(vector, vector)), 1.0, abs_tol=1e-4)


def test_related_texts_score_higher_than_unrelated(embedder: SentenceTransformersEmbedder) -> None:
    algebra, matrices, poetry = embedder.encode(
        [
            "linear algebra and matrices",
            "matrix theory and vector spaces",
            "the history of medieval poetry",
        ]
    )

    assert _dot(algebra, matrices) > _dot(algebra, poetry)
