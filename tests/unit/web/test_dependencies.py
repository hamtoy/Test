"""Tests for FastAPI dependency injection module."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.web.dependencies import (
    ServiceContainer,
    get_app_config,
    get_jinja_env,
    get_agent,
    get_knowledge_graph,
    get_multimodal,
    REPO_ROOT,
)


class TestGetAppConfig:
    """Tests for get_app_config function."""

    def test_get_app_config_returns_config(self) -> None:
        """Test that get_app_config returns an AppConfig instance."""
        # Clear cache to test fresh instantiation
        get_app_config.cache_clear()

        config = get_app_config()

        from src.config import AppConfig

        assert isinstance(config, AppConfig)

    def test_get_app_config_is_cached(self) -> None:
        """Test that get_app_config returns cached instance."""
        get_app_config.cache_clear()

        config1 = get_app_config()
        config2 = get_app_config()

        assert config1 is config2


class TestGetJinjaEnv:
    """Tests for get_jinja_env function."""

    def test_get_jinja_env_returns_environment(self) -> None:
        """Test that get_jinja_env returns a Jinja2 Environment."""
        from jinja2 import Environment

        env = get_jinja_env()

        assert isinstance(env, Environment)

    def test_get_jinja_env_configuration(self) -> None:
        """Test Jinja2 Environment configuration."""
        env = get_jinja_env()

        # Check expected configuration
        assert env.trim_blocks is True
        assert env.lstrip_blocks is True


class TestRepoRoot:
    """Tests for REPO_ROOT constant."""

    def test_repo_root_is_path(self) -> None:
        """Test that REPO_ROOT is a Path."""
        assert isinstance(REPO_ROOT, Path)

    def test_repo_root_exists(self) -> None:
        """Test that REPO_ROOT points to an existing directory."""
        assert REPO_ROOT.exists()


class TestServiceContainer:
    """Tests for ServiceContainer class."""

    def setup_method(self) -> None:
        """Reset ServiceContainer before each test."""
        ServiceContainer.reset()

    def test_reset_clears_all_services(self) -> None:
        """Test that reset clears all service instances."""
        # Set some mock values by direct attribute access
        ServiceContainer._agent = MagicMock()
        ServiceContainer._kg = MagicMock()
        ServiceContainer._mm = MagicMock()

        ServiceContainer.reset()

        # Verify all were reset to None using getattr to avoid mypy narrowing
        assert getattr(ServiceContainer, "_agent") is None
        assert getattr(ServiceContainer, "_kg") is None
        assert getattr(ServiceContainer, "_mm") is None

    def test_get_agent_creates_instance(self) -> None:
        """Test that get_agent creates a GeminiAgent instance."""
        mock_config = MagicMock()
        mock_agent = MagicMock()
        mock_agent_class = MagicMock(return_value=mock_agent)
        mock_module = MagicMock()
        mock_module.GeminiAgent = mock_agent_class

        with (
            patch.dict("sys.modules", {"src.agent": mock_module}),
            patch("src.web.dependencies.get_jinja_env") as mock_jinja,
        ):
            mock_jinja.return_value = MagicMock()

            result = ServiceContainer.get_agent(mock_config)

            assert result is mock_agent
            mock_agent_class.assert_called_once()

    def test_get_agent_returns_cached(self) -> None:
        """Test that get_agent returns cached instance."""
        mock_agent = MagicMock()
        ServiceContainer._agent = mock_agent

        result = ServiceContainer.get_agent(MagicMock())

        assert result is mock_agent

    def test_get_knowledge_graph_creates_instance(self) -> None:
        """Test that get_knowledge_graph creates a QAKnowledgeGraph instance."""
        mock_kg = MagicMock()
        mock_kg_class = MagicMock(return_value=mock_kg)
        mock_module = MagicMock()
        mock_module.QAKnowledgeGraph = mock_kg_class

        with patch.dict("sys.modules", {"src.qa.rag_system": mock_module}):
            result = ServiceContainer.get_knowledge_graph()

            assert result is mock_kg

    def test_get_knowledge_graph_returns_cached(self) -> None:
        """Test that get_knowledge_graph returns cached instance."""
        mock_kg = MagicMock()
        ServiceContainer._kg = mock_kg

        result = ServiceContainer.get_knowledge_graph()

        assert result is mock_kg

    def test_get_knowledge_graph_handles_exception(self) -> None:
        """Test that get_knowledge_graph handles connection failures."""
        mock_kg_class = MagicMock(side_effect=Exception("Connection failed"))
        mock_module = MagicMock()
        mock_module.QAKnowledgeGraph = mock_kg_class

        with patch.dict("sys.modules", {"src.qa.rag_system": mock_module}):
            result = ServiceContainer.get_knowledge_graph()

            assert result is None

    def test_get_multimodal_creates_instance_with_kg(self) -> None:
        """Test that get_multimodal creates instance when KG is available."""
        mock_kg = MagicMock()
        mock_mm = MagicMock()
        mock_mm_class = MagicMock(return_value=mock_mm)
        mock_module = MagicMock()
        mock_module.MultimodalUnderstanding = mock_mm_class
        ServiceContainer._kg = mock_kg

        with patch.dict("sys.modules", {"src.features.multimodal": mock_module}):
            result = ServiceContainer.get_multimodal()

            assert result is mock_mm

    def test_get_multimodal_returns_cached(self) -> None:
        """Test that get_multimodal returns cached instance."""
        mock_mm = MagicMock()
        ServiceContainer._mm = mock_mm

        result = ServiceContainer.get_multimodal()

        assert result is mock_mm

    def test_get_multimodal_returns_none_without_kg(self) -> None:
        """Test that get_multimodal returns None when KG unavailable."""
        # Ensure KG is None
        ServiceContainer._kg = None

        # Mock get_knowledge_graph to return None
        with patch.object(ServiceContainer, "get_knowledge_graph", return_value=None):
            result = ServiceContainer.get_multimodal()

            assert result is None


class TestDependencyFunctions:
    """Tests for FastAPI dependency functions."""

    def setup_method(self) -> None:
        """Reset ServiceContainer before each test."""
        ServiceContainer.reset()

    def test_get_agent_function(self) -> None:
        """Test get_agent dependency function."""
        mock_agent = MagicMock()
        mock_config = MagicMock()

        with patch.object(
            ServiceContainer, "get_agent", return_value=mock_agent
        ) as mock_method:
            result = get_agent(mock_config)

            assert result is mock_agent
            mock_method.assert_called_once_with(mock_config)

    def test_get_knowledge_graph_function(self) -> None:
        """Test get_knowledge_graph dependency function."""
        mock_kg = MagicMock()

        with patch.object(
            ServiceContainer, "get_knowledge_graph", return_value=mock_kg
        ) as mock_method:
            result = get_knowledge_graph()

            assert result is mock_kg
            mock_method.assert_called_once()

    def test_get_multimodal_function(self) -> None:
        """Test get_multimodal dependency function."""
        mock_mm = MagicMock()

        with patch.object(
            ServiceContainer, "get_multimodal", return_value=mock_mm
        ) as mock_method:
            result = get_multimodal()

            assert result is mock_mm
            mock_method.assert_called_once()
