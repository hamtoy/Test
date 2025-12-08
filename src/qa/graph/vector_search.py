"""Vector similarity search module for RAG system.

Provides vector embedding and similarity search capabilities
using LangChain and Neo4j vector indexes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.qa.graph.connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """Vector similarity search engine using Neo4j.

    Provides methods for embedding text and finding similar
    documents in the knowledge graph.

    Args:
        connection_manager: Neo4j connection manager instance
        embedding_model: Name of the embedding model to use
    """

    def __init__(
        self,
        connection_manager: Neo4jConnectionManager,
        embedding_model: str = "text-embedding-ada-002",
    ) -> None:
        """Initialize vector search engine."""
        self.connection = connection_manager
        self.embedding_model = embedding_model
        self._embeddings: Any = None
        self._vector_store: Any = None

    def _init_embeddings(self) -> None:
        """Initialize the embedding model lazily."""
        if self._embeddings is None:
            try:
                from langchain_openai import OpenAIEmbeddings

                self._embeddings = OpenAIEmbeddings(model=self.embedding_model)
                logger.info("Embeddings initialized: %s", self.embedding_model)
            except ImportError:
                logger.warning("langchain_openai not available, vector search disabled")

    def search_similar(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search for similar documents using vector similarity.

        Args:
            query: Search query text
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of similar documents with scores
        """
        self._init_embeddings()

        if self._embeddings is None:
            return []

        try:
            from langchain_neo4j import Neo4jVector

            if self._vector_store is None:
                self._vector_store = Neo4jVector.from_existing_index(
                    self._embeddings,
                    url=self.connection.uri,
                    username=self.connection.user,
                    password=self.connection.password,
                    index_name="rule_embedding",
                )

            results = self._vector_store.similarity_search_with_score(
                query,
                k=k,
            )

            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score,
                }
                for doc, score in results
                if score is not None and score >= score_threshold
            ]
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []

    def embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        self._init_embeddings()

        if self._embeddings is None:
            return None

        try:
            result: list[float] = self._embeddings.embed_query(text)
            return result
        except Exception as e:
            logger.warning("Text embedding failed: %s", e)
            return None
