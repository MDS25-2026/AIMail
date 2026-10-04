"""A Gemini API error (429, 5xx) must surface as the module's own error, not escape as a 500."""

import asyncio

import pytest
from google.genai import errors

from app.rag import embed, generate, reformulate


class _RateLimitedModels:
    def embed_content(self, **_kwargs):
        raise errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})

    generate_content = embed_content


class _RateLimitedClient:
    models = _RateLimitedModels()


@pytest.fixture
def rate_limited(monkeypatch, test_settings):
    for module in (embed, generate, reformulate):
        monkeypatch.setattr(module, "gemini_client", _RateLimitedClient)


def test_rate_limited_embedding_raises_embedding_error(rate_limited):
    with pytest.raises(embed.EmbeddingError):
        asyncio.run(embed.embed_documents(["hello"]))


def test_rate_limited_answer_raises_generation_error(rate_limited):
    chunk = {"source_title": "Policy", "content": "Leave is 14 days."}
    with pytest.raises(generate.GenerationError):
        asyncio.run(generate.answer("How much leave?", [chunk]))


def test_rate_limited_reformulation_falls_back_to_the_question(rate_limited):
    assert asyncio.run(reformulate.reformulate("leave days?")) == "leave days?"
