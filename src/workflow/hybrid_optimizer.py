import logging
from typing import Dict, Any, Literal, cast

# 기존 features 패키지의 LATS 재사용
from src.features.lats import LATSSearcher
from src.workflow.mcts_optimizer import MCTSWorkflowOptimizer
from src.agent.core import GeminiAgent

logger = logging.getLogger(__name__)


class HybridWorkflowOptimizer:
    """
    Orchestrator that routes queries to either LATS (Deep Reasoning)
    or MCTS (Fast Optimization).
    """

    def __init__(self, agent: GeminiAgent, templates: list[str]):
        self.agent = agent
        # LATSSearcher 초기화 (llm_provider로 agent.llm_provider 사용)
        self.lats = LATSSearcher(llm_provider=agent.llm_provider)
        self.mcts = MCTSWorkflowOptimizer(agent, templates)

    async def optimize(
        self, query: str, mode: Literal["auto", "lats", "mcts"] = "auto"
    ) -> Dict[str, Any]:
        """
        Execute optimization based on mode.
        """
        selected_mode: Literal["auto", "lats", "mcts"] = mode
        if mode == "auto":
            detected = self._detect_complexity(query)
            if detected in ["lats", "mcts"]:
                selected_mode = cast(Literal["lats", "mcts"], detected)
            else:
                selected_mode = "mcts"

        logger.info(f"Routing query to: {selected_mode.upper()}")

        if selected_mode == "lats":
            # LATS: Deep reasoning with reflection
            # LATSSearcher.run() 메서드 사용 (SearchNode 반환)
            # 초기 상태에 쿼리를 포함시킬 수 있는지 확인 필요.
            # 현재 SearchState는 turns 리스트를 가짐.
            # 여기서는 단순히 run()을 호출하고 결과 노드를 반환.
            # 실제로는 initial_state에 쿼리를 주입하는 방법이 필요할 수 있음.
            # 하지만 LATSSearcher.run()은 인자 없이도 동작 가능.

            # TODO: 쿼리를 초기 상태로 전달하는 방법 개선 필요 (현재 LATS 구현에 의존)
            # 임시로 run() 호출
            result_node = await self.lats.run()

            return {
                "optimizer": "LATS",
                "result": result_node,  # SearchNode 객체
                "strategy": "Reasoning Tree",
            }
        else:
            # MCTS: Fast template selection
            result = await self.mcts.optimize_workflow(query)
            return {
                "optimizer": "MCTS",
                "best_template": result["best_template"],
                "score": result["score"],
                "strategy": "Template Selection",
            }

    def _detect_complexity(self, query: str) -> str:
        """
        Heuristic for complexity detection.
        """
        # 1. 키워드 기반 탐지
        complex_keywords = [
            "why",
            "explain",
            "reason",
            "compare",
            "analyze",
            "relationship",
        ]
        if any(kw in query.lower() for kw in complex_keywords):
            return "lats"

        # 2. 길이 기반 탐지 (긴 컨텍스트는 추론이 필요할 가능성 높음)
        if len(query.split()) > 50:
            return "lats"

        # 3. 기본값: 단순 정보 추출이나 포맷팅은 MCTS로 처리
        return "mcts"
