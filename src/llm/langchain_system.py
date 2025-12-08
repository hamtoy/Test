from __future__ import annotations

from typing import Any

from src.features.self_correcting import SelfCorrectingQAChain
from src.llm.gemini import GeminiModelClient
from src.llm.lcel_chain import LCELOptimizedChain
from src.qa.factory import QASystemFactory
from src.qa.memory_augmented import MemoryAugmentedQASystem
from src.qa.multi_agent import MultiAgentQASystem
from src.qa.rag_system import QAKnowledgeGraph
from src.routing.graph_router import GraphEnhancedRouter


class UltimateLangChainQASystem:
    """Gemini + KG 기반으로 구성한 통합 QA 시스템.

    Uses QASystemFactory for component creation to reduce coupling
    and improve maintainability.
    """

    kg: Any
    memory_system: Any
    agent_system: Any
    correcting_chain: Any
    router: Any
    lcel_chain: Any

    def __init__(
        self,
        neo4j_uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        factory: QASystemFactory | None = None,
    ):
        """Initialize the Ultimate QA System with all components.

        Args:
            neo4j_uri: Optional Neo4j database URI
            user: Optional Neo4j username
            password: Optional Neo4j password
            factory: Optional QASystemFactory instance for dependency injection
        """
        if factory is not None:
            components = factory.create_all_components()
            self.kg = components["knowledge_graph"]
            self.memory_system = components["memory_system"]
            self.agent_system = components["agent_system"]
            self.correcting_chain = components["correcting_chain"]
            self.router = components["router"]
            self.lcel_chain = components["lcel_chain"]
            return

        def _construct(cls: type[Any], *args: Any) -> Any:
            try:
                return cls(*args)
            except TypeError:
                return cls()

        self.kg = _construct(QAKnowledgeGraph, neo4j_uri, user, password)
        model_client = _construct(GeminiModelClient)
        self.memory_system = _construct(
            MemoryAugmentedQASystem, neo4j_uri, user, password,
        )
        self.agent_system = _construct(MultiAgentQASystem, self.kg)
        self.correcting_chain = _construct(SelfCorrectingQAChain, self.kg, model_client)
        self.router = _construct(GraphEnhancedRouter, self.kg, model_client)
        self.lcel_chain = _construct(LCELOptimizedChain, self.kg, model_client)

    def generate_ultimate_qa(
        self, image_path: str, user_query: str | None = None,
    ) -> dict[str, Any]:
        """모든 기능을 활용한 최상급 생성."""
        # 1. 라우터로 질의 유형 자동 판단 (핸들러 기본값 제공해 빈 핸들러 오류 방지)
        router_handlers = {
            "explanation": lambda text: None,
            "summary": lambda text: None,
            "explore": lambda text: None,
        }
        routed = self.router.route_and_generate(
            user_query or "explanation", handlers=router_handlers,
        )
        query_type = routed.get("choice", "explanation")

        # 2. Multi-Agent로 정보 수집
        agent_result = self.agent_system.collaborative_generate(
            query_type,
            {"image_path": image_path},
        )

        # 3. Self-Correction으로 생성 및 교정
        corrected = self.correcting_chain.generate_with_self_correction(
            query_type, agent_result.get("metadata", {}),
        )

        # 4. Memory에 기록 (학습)
        self.memory_system._log_interaction(
            user_query or f"Generate {query_type}", corrected["output"],
        )

        return {
            "output": corrected["output"],
            "query_type": query_type,
            "metadata": {
                **agent_result.get("metadata", {}),
                "iterations": corrected.get("iterations"),
                "validation": corrected.get("validation"),
            },
        }
