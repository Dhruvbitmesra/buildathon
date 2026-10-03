import pytest

from app.agents.schema_mapping.groq_client import (
    DEFAULT_MODEL,
    GroqLLMClient,
)


def test_default_model():

    assert DEFAULT_MODEL == "openai/gpt-oss-120b"


def test_missing_api_key(monkeypatch):

    monkeypatch.delenv(
        "GROQ_API_KEY",
        raising=False,
    )

    with pytest.raises(ValueError, match="GROQ_API_KEY"):

        GroqLLMClient()


def test_explicit_api_key():

    client = GroqLLMClient(
        api_key="test-key",
    )

    assert client.model == "openai/gpt-oss-120b"
    assert client.client is not None


def test_custom_model():

    client = GroqLLMClient(
        model="openai/gpt-oss-120b",
        api_key="test-key",
    )

    assert client.model == "openai/gpt-oss-120b"