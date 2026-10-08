"""A model failure (429, 5xx, Ollama down) surfaces as a coded error or a fallback, never as a 500."""

import asyncio

import pytest
from google.genai import errors

import model_gateway
from app.core.providers import Provider
from app.rag import embed, generate, reformulate
from model_runtime import ModelError, ModelErrorCode


class _RateLimitedModels:
    def embed_content(self, **_kwargs):
        raise errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})

    generate_content = embed_content


class _RateLimitedClient:
    models = _RateLimitedModels()


@pytest.fixture
def rate_limited(monkeypatch, test_settings):
    async def unavailable(*_args, **_kwargs):
        raise ModelError(ModelErrorCode.UNAVAILABLE, "quota")

    monkeypatch.setattr(embed, "gemini_client", _RateLimitedClient)
    monkeypatch.setattr(model_gateway, "gemini_generate", unavailable)


def test_rate_limited_embedding_raises_embedding_error(rate_limited):
    with pytest.raises(embed.EmbeddingError):
        asyncio.run(embed.embed_documents(["hello"]))


def test_a_failed_answer_raises_the_shared_model_error(rate_limited):
    chunk = {"source_title": "Policy", "content": "Leave is 14 days."}
    with pytest.raises(ModelError):
        asyncio.run(generate.answer("How much leave?", [chunk], provider=Provider.GEMINI))


def test_rate_limited_reformulation_falls_back_to_the_question(rate_limited):
    assert asyncio.run(reformulate.reformulate("leave days?", provider=Provider.GEMINI)) == "leave days?"
