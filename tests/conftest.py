import pytest


@pytest.fixture(autouse=True)
def isolated_mapping_memory(tmp_path, monkeypatch):
    """Keep every test away from the real memory/mapping_memory.json."""

    monkeypatch.setenv("SOV_MEMORY_PATH", str(tmp_path / "mapping_memory.json"))


@pytest.fixture(autouse=True)
def unlimited_llm_budget():
    """Fake LLM clients must not wait on the real per-minute token budget."""

    from app.llm_rate_limiter import RATE_LIMITER

    RATE_LIMITER.reset(tokens_per_minute=10**9)
    yield
    RATE_LIMITER.reset(tokens_per_minute=10**9)
