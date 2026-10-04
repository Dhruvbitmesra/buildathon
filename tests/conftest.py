import pytest


@pytest.fixture(autouse=True)
def isolated_mapping_memory(tmp_path, monkeypatch):
    """Keep every test away from the real memory/mapping_memory.json."""

    monkeypatch.setenv("SOV_MEMORY_PATH", str(tmp_path / "mapping_memory.json"))
