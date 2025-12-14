"""QA System Component Factory module.

Centralized factory for instantiating QA components:
- KnowledgeGraph, MemorySystem, MultiAgentSystem, Router, LCELChain.
Provides context manager support for automatic resource cleanup.
"""

from __future__ import annotations

from contextlib import suppress

from src.features.self_correcting import SelfCorrectingQAChain
from src.llm.gemini import GeminiModelClient
from src.llm.lcel_chain import LCELOptimizedChain
from src.qa.memory_augmented import MemoryAugmentedQASystem
from src.qa.multi_agent import MultiAgentQASystem
from src.qa.rag_system import QAKnowledgeGraph
from src.routing.graph_router import GraphEnhancedRouter


class QASystemFactory:
    """Factory class for creating QA system components.

    Centralizes the instantiation logic for all QA components,
    reducing coupling and improving testability.

    Example:
        with QASystemFactory() as factory:
            kg = factory.get_knowledge_graph()
            # 작업 수행
        # with 블록 종료 시 자동으로 리소스가 정리됩니다.
    """

    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
    ):
        """Initialize the factory with optional Neo4j credentials.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # Shared dependencies
        self._kg: QAKnowledgeGraph | None = None
        self._model_client: GeminiModelClient | None = None

    def get_knowledge_graph(self) -> QAKnowledgeGraph:
        """Get or create the shared QAKnowledgeGraph instance.

        Returns:
            QAKnowledgeGraph instance
        """
        if self._kg is None:
            self._kg = QAKnowledgeGraph()
        return self._kg

    def get_model_client(self) -> GeminiModelClient:
        """Get or create the shared GeminiModelClient instance.

        Returns:
            GeminiModelClient instance
        """
        if self._model_client is None:
            self._model_client = GeminiModelClient()
        return self._model_client

    def create_memory_system(self) -> MemoryAugmentedQASystem:
        """Create a MemoryAugmentedQASystem instance.

        Returns:
            MemoryAugmentedQASystem instance configured with Neo4j credentials
        """
        return MemoryAugmentedQASystem(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

    def create_agent_system(self) -> MultiAgentQASystem:
        """Create a MultiAgentQASystem instance.

        Returns:
            MultiAgentQASystem instance using the shared knowledge graph
        """
        return MultiAgentQASystem(self.get_knowledge_graph())

    def create_correcting_chain(self) -> SelfCorrectingQAChain:
        """Create a SelfCorrectingQAChain instance.

        Returns:
            SelfCorrectingQAChain instance using shared dependencies
        """
        return SelfCorrectingQAChain(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_router(self) -> GraphEnhancedRouter:
        """Create a GraphEnhancedRouter instance.

        Returns:
            GraphEnhancedRouter instance using shared dependencies
        """
        return GraphEnhancedRouter(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_lcel_chain(self) -> LCELOptimizedChain:
        """Create a LCELOptimizedChain instance.

        Returns:
            LCELOptimizedChain instance using shared dependencies
        """
        return LCELOptimizedChain(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_all_components(self) -> dict[str, object]:
        """Create all QA system components at once.

        Returns:
            Dictionary containing all initialized components with keys:
            - 'knowledge_graph': QAKnowledgeGraph
            - 'memory_system': MemoryAugmentedQASystem
            - 'agent_system': MultiAgentQASystem
            - 'correcting_chain': SelfCorrectingQAChain
            - 'router': GraphEnhancedRouter
            - 'lcel_chain': LCELOptimizedChain
        """
        return {
            "knowledge_graph": self.get_knowledge_graph(),
            "memory_system": self.create_memory_system(),
            "agent_system": self.create_agent_system(),
            "correcting_chain": self.create_correcting_chain(),
            "router": self.create_router(),
            "lcel_chain": self.create_lcel_chain(),
        }

    def close(self) -> None:
        """모든 공유 리소스를 정리합니다."""
        if self._kg is not None:
            with suppress(Exception):
                self._kg.close()
            self._kg = None

        if self._model_client is not None:
            close_client = getattr(self._model_client, "close", None)
            if callable(close_client):
                with suppress(Exception):
                    close_client()
            self._model_client = None

    def __enter__(self) -> QASystemFactory:
        """컨텍스트 매니저 진입 시 팩토리 인스턴스 반환."""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        _exc_val: BaseException | None,
        _exc_tb: object | None,
    ) -> None:
        """컨텍스트 종료 시 리소스 정리."""
        self.close()

    def __del__(self) -> None:
        """파괴자에서 안전하게 리소스를 정리합니다."""
        with suppress(Exception):
            self.close()
