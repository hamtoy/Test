"""Tests for the QA factory module."""

from unittest.mock import MagicMock, patch

import pytest


class TestQASystemFactory:
    """Tests for QASystemFactory class."""

    @pytest.fixture
    def factory(self):
        """Create a factory instance with mock credentials."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph"),
            patch("src.qa.factory.GeminiModelClient"),
        ):
            from src.qa.factory import QASystemFactory

            return QASystemFactory(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
            )

    def test_init_without_credentials(self):
        """Test factory initialization without credentials."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph"),
            patch("src.qa.factory.GeminiModelClient"),
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()
            assert factory.neo4j_uri is None
            assert factory.neo4j_user is None
            assert factory.neo4j_password is None

    def test_init_with_credentials(self):
        """Test factory initialization with credentials."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph"),
            patch("src.qa.factory.GeminiModelClient"),
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
            )
            assert factory.neo4j_uri == "bolt://localhost:7687"
            assert factory.neo4j_user == "neo4j"
            assert factory.neo4j_password == "password"

    def test_get_knowledge_graph_creates_instance(self):
        """Test that get_knowledge_graph creates a new instance."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient"),
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_kg = MagicMock()
            MockKG.return_value = mock_kg

            kg1 = factory.get_knowledge_graph()
            kg2 = factory.get_knowledge_graph()

            # Should return the same cached instance
            assert kg1 is kg2
            MockKG.assert_called_once()

    def test_get_model_client_creates_instance(self):
        """Test that get_model_client creates a new instance."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph"),
            patch("src.qa.factory.GeminiModelClient") as MockClient,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client1 = factory.get_model_client()
            client2 = factory.get_model_client()

            # Should return the same cached instance
            assert client1 is client2
            MockClient.assert_called_once()

    def test_create_memory_system(self):
        """Test creation of MemoryAugmentedQASystem."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph"),
            patch("src.qa.factory.GeminiModelClient"),
            patch("src.qa.factory.MemoryAugmentedQASystem") as MockMemory,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
            )

            mock_system = MagicMock()
            MockMemory.return_value = mock_system

            result = factory.create_memory_system()

            assert result is mock_system
            MockMemory.assert_called_once_with(
                "bolt://localhost:7687",
                "neo4j",
                "password",
            )

    def test_create_agent_system(self):
        """Test creation of MultiAgentQASystem."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient"),
            patch("src.qa.factory.MultiAgentQASystem") as MockAgent,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_kg = MagicMock()
            MockKG.return_value = mock_kg

            mock_system = MagicMock()
            MockAgent.return_value = mock_system

            result = factory.create_agent_system()

            assert result is mock_system
            MockAgent.assert_called_once_with(mock_kg)

    def test_create_correcting_chain(self):
        """Test creation of SelfCorrectingQAChain."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient") as MockClient,
            patch("src.qa.factory.SelfCorrectingQAChain") as MockChain,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_kg = MagicMock()
            mock_client = MagicMock()
            MockKG.return_value = mock_kg
            MockClient.return_value = mock_client

            mock_chain = MagicMock()
            MockChain.return_value = mock_chain

            result = factory.create_correcting_chain()

            assert result is mock_chain
            MockChain.assert_called_once_with(mock_kg, mock_client)

    def test_create_router(self):
        """Test creation of GraphEnhancedRouter."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient") as MockClient,
            patch("src.qa.factory.GraphEnhancedRouter") as MockRouter,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_kg = MagicMock()
            mock_client = MagicMock()
            MockKG.return_value = mock_kg
            MockClient.return_value = mock_client

            mock_router = MagicMock()
            MockRouter.return_value = mock_router

            result = factory.create_router()

            assert result is mock_router
            MockRouter.assert_called_once_with(mock_kg, mock_client)

    def test_create_lcel_chain(self):
        """Test creation of LCELOptimizedChain."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient") as MockClient,
            patch("src.qa.factory.LCELOptimizedChain") as MockLCEL,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory()

            mock_kg = MagicMock()
            mock_client = MagicMock()
            MockKG.return_value = mock_kg
            MockClient.return_value = mock_client

            mock_lcel = MagicMock()
            MockLCEL.return_value = mock_lcel

            result = factory.create_lcel_chain()

            assert result is mock_lcel
            MockLCEL.assert_called_once_with(mock_kg, mock_client)

    def test_create_all_components(self):
        """Test creation of all components at once."""
        with (
            patch("src.qa.factory.QAKnowledgeGraph") as MockKG,
            patch("src.qa.factory.GeminiModelClient") as MockClient,
            patch("src.qa.factory.MemoryAugmentedQASystem") as MockMemory,
            patch("src.qa.factory.MultiAgentQASystem") as MockAgent,
            patch("src.qa.factory.SelfCorrectingQAChain") as MockChain,
            patch("src.qa.factory.GraphEnhancedRouter") as MockRouter,
            patch("src.qa.factory.LCELOptimizedChain") as MockLCEL,
        ):
            from src.qa.factory import QASystemFactory

            factory = QASystemFactory(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
            )

            # Configure mocks
            mock_kg = MagicMock()
            MockKG.return_value = mock_kg

            mock_client = MagicMock()
            MockClient.return_value = mock_client

            components = factory.create_all_components()

            assert "knowledge_graph" in components
            assert "memory_system" in components
            assert "agent_system" in components
            assert "correcting_chain" in components
            assert "router" in components
            assert "lcel_chain" in components

            # Verify all creation methods were called
            MockMemory.assert_called_once()
            MockAgent.assert_called_once()
            MockChain.assert_called_once()
            MockRouter.assert_called_once()
            MockLCEL.assert_called_once()
