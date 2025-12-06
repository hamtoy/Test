"""Tests for src/web/dependencies.py to increase coverage."""

from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.web.dependencies import ServiceRegistry


class TestServiceRegistryCoverage:
    """Test ServiceRegistry uncovered exception paths."""

    def setup_method(self) -> None:
        """Reset ServiceRegistry state before each test."""
        ServiceRegistry._config = None
        ServiceRegistry._agent = None
        ServiceRegistry._kg = None
        ServiceRegistry._pipeline = None

    @patch("src.web.dependencies.Agent")
    @patch("src.web.dependencies.get_app_config")
    @patch("src.web.dependencies.Environment")
    def test_get_agent_exception(
        self,
        mock_env: MagicMock,
        mock_get_config: MagicMock,
        mock_agent_class: MagicMock,
    ) -> None:
        """Test get_agent handles exceptions."""
        mock_agent_class.side_effect = Exception("Agent creation failed")
        
        result = ServiceRegistry.get_agent()
        
        assert result is None

    @patch("src.web.dependencies.QAKnowledgeGraph")
    def test_get_knowledge_graph_exception(
        self, mock_kg_class: MagicMock
    ) -> None:
        """Test get_knowledge_graph handles exceptions."""
        with patch.dict("sys.modules", {"src.qa.rag_system": MagicMock()}):
            with patch(
                "src.qa.rag_system.QAKnowledgeGraph", side_effect=Exception("KG init failed")
            ):
                result = ServiceRegistry.get_knowledge_graph()
                assert result is None

    @patch("src.web.dependencies.IntegratedQAPipeline")
    def test_get_pipeline_exception(self, mock_pipeline_class: MagicMock) -> None:
        """Test get_pipeline handles exceptions."""
        with patch.dict("sys.modules", {"src.qa.pipeline": MagicMock()}):
            with patch(
                "src.qa.pipeline.IntegratedQAPipeline",
                side_effect=Exception("Pipeline init failed"),
            ):
                result = ServiceRegistry.get_pipeline()
                assert result is None

    def test_set_and_get_config(self) -> None:
        """Test set_config and get_config."""
        from src.config.settings import AppConfig
        
        config = MagicMock(spec=AppConfig)
        ServiceRegistry.set_config(config)
        
        assert ServiceRegistry.get_config() == config

    def test_set_and_get_agent(self) -> None:
        """Test set_agent and get_agent."""
        from src.agent.main import GeminiAgent
        
        agent = MagicMock(spec=GeminiAgent)
        ServiceRegistry.set_agent(agent)
        
        assert ServiceRegistry.get_agent() == agent

    def test_set_and_get_kg(self) -> None:
        """Test set_kg and get_knowledge_graph."""
        kg = MagicMock()
        ServiceRegistry.set_kg(kg)
        
        assert ServiceRegistry.get_knowledge_graph() == kg

    def test_set_and_get_pipeline(self) -> None:
        """Test set_pipeline and get_pipeline."""
        pipeline = MagicMock()
        ServiceRegistry.set_pipeline(pipeline)
        
        assert ServiceRegistry.get_pipeline() == pipeline

    def test_set_kg_none(self) -> None:
        """Test set_kg with None."""
        ServiceRegistry.set_kg(None)
        assert ServiceRegistry._kg is None

    def test_set_pipeline_none(self) -> None:
        """Test set_pipeline with None."""
        ServiceRegistry.set_pipeline(None)
        assert ServiceRegistry._pipeline is None
