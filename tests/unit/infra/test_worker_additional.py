"""Additional tests for src/infra/worker.py to improve coverage."""

import pytest

# Import faststream if available, skip tests if not
pytest.importorskip("faststream")


def test_worker_init_providers_with_llm_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _init_providers with LLM provider enabled."""
    from src.infra import worker

    # Reset the flag to allow re-initialization
    worker._providers_initialized = False
    
    # Mock config with llm_provider_enabled=True
    class MockConfig:
        llm_provider_enabled = True
        gemini_api_key = "test_key_AIzaSyDtest1234567890123456789012345"
        gemini_model_name = "gemini-flash-latest"
        enable_data2neo = False
    
    monkeypatch.setattr(worker, "get_config", lambda: MockConfig())
    monkeypatch.setattr(worker, "get_llm_provider", lambda config: None)
    
    # Call init_providers
    worker._init_providers()
    
    # Verify it was initialized
    assert worker._providers_initialized is True
    
    # Reset for other tests
    worker._providers_initialized = False


def test_worker_init_providers_with_data2neo_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _init_providers with Data2Neo enabled."""
    from src.infra import worker

    # Reset the flag
    worker._providers_initialized = False
    
    # Mock config with enable_data2neo=True
    class MockConfig:
        llm_provider_enabled = False
        enable_data2neo = True
        gemini_api_key = "test_key_AIzaSyDtest1234567890123456789012345"
    
    monkeypatch.setattr(worker, "get_config", lambda: MockConfig())
    monkeypatch.setattr(worker, "get_graph_provider", lambda config: None)
    
    # Call init_providers
    worker._init_providers()
    
    assert worker._providers_initialized is True
    
    # Reset
    worker._providers_initialized = False


def test_worker_init_providers_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _init_providers handles exceptions gracefully."""
    from src.infra import worker

    # Reset the flag
    worker._providers_initialized = False
    
    # Mock config that will trigger exceptions
    class MockConfig:
        llm_provider_enabled = True
        enable_data2neo = False
        gemini_api_key = "test_key"
    
    def mock_get_llm_provider(config: object) -> None:
        raise RuntimeError("LLM provider error")
    
    monkeypatch.setattr(worker, "get_config", lambda: MockConfig())
    monkeypatch.setattr(worker, "get_llm_provider", mock_get_llm_provider)
    
    # Should not raise, just log warning
    worker._init_providers()
    
    assert worker._providers_initialized is True
    
    # Reset
    worker._providers_initialized = False
