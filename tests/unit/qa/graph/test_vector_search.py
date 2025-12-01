"""Tests for vector similarity search module."""

from unittest.mock import MagicMock, patch

import pytest

from src.qa.graph.connection import Neo4jConnectionManager
from src.qa.graph.vector_search import VectorSearchEngine


class TestVectorSearchEngine:
    """Tests for VectorSearchEngine class."""

    @pytest.fixture
    def mock_connection(self) -> Neo4jConnectionManager:
        """Create a mock connection manager."""
        connection = MagicMock(spec=Neo4jConnectionManager)
        connection.uri = "bolt://test:7687"
        connection.user = "testuser"
        connection.password = "testpass"
        return connection

    def test_init(self, mock_connection: Neo4jConnectionManager) -> None:
        """Test initialization with default embedding model."""
        engine = VectorSearchEngine(mock_connection)

        assert engine.connection is mock_connection
        assert engine.embedding_model == "text-embedding-ada-002"
        assert engine._embeddings is None
        assert engine._vector_store is None

    def test_init_custom_model(self, mock_connection: Neo4jConnectionManager) -> None:
        """Test initialization with custom embedding model."""
        engine = VectorSearchEngine(
            mock_connection,
            embedding_model="custom-model",
        )

        assert engine.embedding_model == "custom-model"

    def test_init_embeddings_success(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test lazy initialization of embeddings."""
        mock_embeddings = MagicMock()
        mock_openai_embeddings = MagicMock(return_value=mock_embeddings)
        mock_module = MagicMock()
        mock_module.OpenAIEmbeddings = mock_openai_embeddings

        with patch.dict("sys.modules", {"langchain_openai": mock_module}):
            engine = VectorSearchEngine(mock_connection)
            engine._init_embeddings()

            assert engine._embeddings is mock_embeddings
            mock_openai_embeddings.assert_called_once_with(
                model="text-embedding-ada-002"
            )

    def test_init_embeddings_import_error(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test embeddings initialization handles import error gracefully."""
        # Ensure the import fails by setting the module to None
        with patch.dict(
            "sys.modules",
            {"langchain_openai": None},
            clear=False,
        ):
            engine = VectorSearchEngine(mock_connection)
            engine._init_embeddings()

            assert engine._embeddings is None

    def test_search_similar_no_embeddings(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test search_similar returns empty when embeddings unavailable."""
        engine = VectorSearchEngine(mock_connection)

        with patch.object(engine, "_init_embeddings"):
            engine._embeddings = None
            results = engine.search_similar("test query")

            assert results == []

    def test_search_similar_success(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test successful similarity search."""
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Content 1"
        mock_doc1.metadata = {"id": "1"}

        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Content 2"
        mock_doc2.metadata = {"id": "2"}

        mock_vector_store = MagicMock()
        mock_vector_store.similarity_search_with_score.return_value = [
            (mock_doc1, 0.9),
            (mock_doc2, 0.8),
        ]

        mock_neo4j_vector = MagicMock()
        mock_neo4j_vector.from_existing_index.return_value = mock_vector_store

        mock_module = MagicMock()
        mock_module.Neo4jVector = mock_neo4j_vector

        mock_embeddings = MagicMock()

        with patch.dict("sys.modules", {"langchain_neo4j": mock_module}):
            engine = VectorSearchEngine(mock_connection)
            engine._embeddings = mock_embeddings

            results = engine.search_similar("test query", k=5, score_threshold=0.7)

            assert len(results) == 2
            assert results[0]["content"] == "Content 1"
            assert results[0]["score"] == 0.9
            assert results[0]["metadata"] == {"id": "1"}
            assert results[1]["content"] == "Content 2"

    def test_search_similar_filters_by_threshold(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test that search_similar filters results by score threshold."""
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "High score content"
        mock_doc1.metadata = {}

        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Low score content"
        mock_doc2.metadata = {}

        mock_vector_store = MagicMock()
        mock_vector_store.similarity_search_with_score.return_value = [
            (mock_doc1, 0.9),
            (mock_doc2, 0.5),  # Below threshold
        ]

        mock_neo4j_vector = MagicMock()
        mock_neo4j_vector.from_existing_index.return_value = mock_vector_store

        mock_module = MagicMock()
        mock_module.Neo4jVector = mock_neo4j_vector

        mock_embeddings = MagicMock()

        with patch.dict("sys.modules", {"langchain_neo4j": mock_module}):
            engine = VectorSearchEngine(mock_connection)
            engine._embeddings = mock_embeddings

            results = engine.search_similar("test", score_threshold=0.7)

            assert len(results) == 1
            assert results[0]["content"] == "High score content"

    def test_search_similar_exception(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test search_similar handles exceptions gracefully."""
        mock_embeddings = MagicMock()

        mock_neo4j_vector = MagicMock()
        mock_neo4j_vector.from_existing_index.side_effect = Exception(
            "Vector search error"
        )

        mock_module = MagicMock()
        mock_module.Neo4jVector = mock_neo4j_vector

        with patch.dict("sys.modules", {"langchain_neo4j": mock_module}):
            engine = VectorSearchEngine(mock_connection)
            engine._embeddings = mock_embeddings

            results = engine.search_similar("test query")

            assert results == []

    def test_embed_text_no_embeddings(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test embed_text returns None when embeddings unavailable."""
        engine = VectorSearchEngine(mock_connection)

        with patch.object(engine, "_init_embeddings"):
            engine._embeddings = None
            result = engine.embed_text("test text")

            assert result is None

    def test_embed_text_success(self, mock_connection: Neo4jConnectionManager) -> None:
        """Test successful text embedding."""
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        engine = VectorSearchEngine(mock_connection)
        engine._embeddings = mock_embeddings

        result = engine.embed_text("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_embeddings.embed_query.assert_called_once_with("test text")

    def test_embed_text_exception(
        self, mock_connection: Neo4jConnectionManager
    ) -> None:
        """Test embed_text handles exceptions gracefully."""
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.side_effect = Exception("Embedding error")

        engine = VectorSearchEngine(mock_connection)
        engine._embeddings = mock_embeddings

        result = engine.embed_text("test text")

        assert result is None
