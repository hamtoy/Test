from __future__ import annotations

from typing import Dict, Optional

from src.llm.gemini import GeminiModelClient
from src.routing.graph_router import GraphEnhancedRouter
from src.llm.lcel_chain import LCELOptimizedChain
from src.qa.memory_augmented import MemoryAugmentedQASystem
from src.qa.multi_agent import MultiAgentQASystem
from src.qa.rag_system import QAKnowledgeGraph
from src.features.self_correcting import SelfCorrectingQAChain


class QASystemFactory:
    """
    Factory class for creating QA system components.

    Centralizes the instantiation logic for all QA components,
    reducing coupling and improving testability.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
    ):
        """
        Initialize the factory with optional Neo4j credentials.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # Shared dependencies
        self._kg: Optional[QAKnowledgeGraph] = None
        self._model_client: Optional[GeminiModelClient] = None

    def get_knowledge_graph(self) -> QAKnowledgeGraph:
        """
        Get or create the shared QAKnowledgeGraph instance.

        Returns:
            QAKnowledgeGraph instance
        """
        if self._kg is None:
            self._kg = QAKnowledgeGraph()
        return self._kg

    def get_model_client(self) -> GeminiModelClient:
        """
        Get or create the shared GeminiModelClient instance.

        Returns:
            GeminiModelClient instance
        """
        if self._model_client is None:
            self._model_client = GeminiModelClient()
        return self._model_client

    def create_memory_system(self) -> MemoryAugmentedQASystem:
        """
        Create a MemoryAugmentedQASystem instance.

        Returns:
            MemoryAugmentedQASystem instance configured with Neo4j credentials
        """
        return MemoryAugmentedQASystem(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

    def create_agent_system(self) -> MultiAgentQASystem:
        """
        Create a MultiAgentQASystem instance.

        Returns:
            MultiAgentQASystem instance using the shared knowledge graph
        """
        return MultiAgentQASystem(self.get_knowledge_graph())

    def create_correcting_chain(self) -> SelfCorrectingQAChain:
        """
        Create a SelfCorrectingQAChain instance.

        Returns:
            SelfCorrectingQAChain instance using shared dependencies
        """
        return SelfCorrectingQAChain(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_router(self) -> GraphEnhancedRouter:
        """
        Create a GraphEnhancedRouter instance.

        Returns:
            GraphEnhancedRouter instance using shared dependencies
        """
        return GraphEnhancedRouter(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_lcel_chain(self) -> LCELOptimizedChain:
        """
        Create a LCELOptimizedChain instance.

        Returns:
            LCELOptimizedChain instance using shared dependencies
        """
        return LCELOptimizedChain(
            self.get_knowledge_graph(),
            self.get_model_client(),
        )

    def create_all_components(self) -> Dict[str, object]:
        """
        Create all QA system components at once.

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
