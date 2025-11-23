from __future__ import annotations

from typing import Any, Dict, Optional

from src.gemini_model_client import GeminiModelClient
from src.graph_enhanced_router import GraphEnhancedRouter
from src.lcel_optimized_chain import LCELOptimizedChain
from src.memory_augmented_qa import MemoryAugmentedQASystem
from src.multi_agent_qa_system import MultiAgentQASystem
from src.qa_rag_system import QAKnowledgeGraph
from src.self_correcting_chain import SelfCorrectingQAChain


class UltimateLangChainQASystem:
    """
    Gemini + KG 기반으로 구성한 통합 QA 시스템.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.kg = QAKnowledgeGraph()

        # 1. Memory
        self.memory_system = MemoryAugmentedQASystem(neo4j_uri, user, password)

        # 2. Multi-Agent (간소화)
        self.agent_system = MultiAgentQASystem(self.kg)

        # 3. Self-Correction
        self.correcting_chain = SelfCorrectingQAChain(self.kg, GeminiModelClient())

        # 4. Router
        self.router = GraphEnhancedRouter(self.kg, GeminiModelClient())

        # 5. LCEL
        self.lcel_chain = LCELOptimizedChain(self.kg, GeminiModelClient())

    def generate_ultimate_qa(
        self, image_path: str, user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        모든 기능을 활용한 최상급 생성.
        """

        # 1. 라우터로 질의 유형 자동 판단
        if user_query:
            routed = self.router.route_and_generate(user_query, handlers={})
            query_type = routed.get("choice", "explanation")
        else:
            query_type = "explanation"

        # 2. Multi-Agent로 정보 수집
        agent_result = self.agent_system.collaborative_generate(
            query_type,
            {"image_path": image_path},
        )

        # 3. Self-Correction으로 생성 및 교정
        corrected = self.correcting_chain.generate_with_self_correction(
            query_type, agent_result.get("metadata", {})
        )

        # 4. Memory에 기록 (학습)
        self.memory_system._log_interaction(
            user_query or f"Generate {query_type}", corrected["output"]
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
