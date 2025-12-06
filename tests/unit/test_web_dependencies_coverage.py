"""Tests for src/web/dependencies.py to increase coverage."""

from typing import Optional
from unittest.mock import MagicMock, patch


from src.web.dependencies import ServiceContainer


class TestServiceContainerCoverage:
    """Test ServiceContainer uncovered exception paths."""

    def setup_method(self) -> None:
        """Reset ServiceContainer state before each test."""
        ServiceContainer._config = None
        ServiceContainer._agent = None
        ServiceContainer._kg = None
        ServiceContainer._pipeline = None

    @patch("src.web.dependencies.GeminiAgent")
    @patch("src.web.dependencies.get_app_config")
    @patch("src.web.dependencies.get_jinja_env")
    def test_get_agent_exception(
        self,
        mock_env: MagicMock,
        mock_get_config: MagicMock,
        mock_agent_class: MagicMock,
    ) -> None:
        """Test get_agent handles exceptions."""
        mock_agent_class.side_effect = Exception("Agent creation failed")

        result: Optional[object] = ServiceContainer.get_agent()

        assert result is None

    def test_get_knowledge_graph_exception(self) -> None:
        """Test get_knowledge_graph handles exceptions."""
        with (
            patch.dict("sys.modules", {"src.qa.rag_system": MagicMock()}),
            patch(
                "src.qa.rag_system.QAKnowledgeGraph",
                side_effect=Exception("KG init failed"),
            ),
        ):
            result: Optional[object] = ServiceContainer.get_knowledge_graph()
            assert result is None

    def test_get_pipeline_exception(self) -> None:
        """Test get_pipeline handles exceptions."""
        with (
            patch.dict("sys.modules", {"src.qa.pipeline": MagicMock()}),
            patch(
                "src.qa.pipeline.IntegratedQAPipeline",
                side_effect=Exception("Pipeline init failed"),
            ),
        ):
            result: Optional[object] = ServiceContainer.get_pipeline()
            assert result is None

    def test_set_and_get_config(self) -> None:
        """Test set_config and get_config."""
        from src.config.settings import AppConfig

        config = MagicMock(spec=AppConfig)
        ServiceContainer.set_config(config)

        assert ServiceContainer.get_config() == config

    def test_set_and_get_agent(self) -> None:
        """Test set_agent and get_agent."""
        from src.agent import GeminiAgent

        agent = MagicMock(spec=GeminiAgent)
        ServiceContainer.set_agent(agent)

        assert ServiceContainer.get_agent() == agent

    def test_set_and_get_kg(self) -> None:
        """Test set_kg and get_knowledge_graph."""
        kg = MagicMock()
        ServiceContainer.set_kg(kg)

        assert ServiceContainer.get_knowledge_graph() == kg

    def test_set_and_get_pipeline(self) -> None:
        """Test set_pipeline and get_pipeline."""
        pipeline = MagicMock()
        ServiceContainer.set_pipeline(pipeline)

        assert ServiceContainer.get_pipeline() == pipeline

    def test_set_kg_none(self) -> None:
        """Test set_kg with None."""
        ServiceContainer.set_kg(None)
        assert ServiceContainer._kg is None

    def test_set_pipeline_none(self) -> None:
        """Test set_pipeline with None."""
        ServiceContainer.set_pipeline(None)
        assert ServiceContainer._pipeline is None
