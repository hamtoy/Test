import logging
from typing import Dict, Any, Literal, Optional, cast

# 기존 features 패키지의 LATS 재사용
from src.features.lats import LATSSearcher, SearchState
from src.workflow.mcts_optimizer import MCTSWorkflowOptimizer
from src.agent.core import GeminiAgent

logger = logging.getLogger(__name__)


class HybridWorkflowOptimizer:
    """Orchestrator that routes queries to either LATS (Deep Reasoning)
    or MCTS (Fast Optimization).
    """

    def __init__(self, agent: GeminiAgent, templates: list[str]):
        self.agent = agent
        # LATSSearcher 초기화 (llm_provider로 agent.llm_provider 사용)
        self.lats = LATSSearcher(llm_provider=agent.llm_provider)
        self.mcts = MCTSWorkflowOptimizer(agent, templates)

    async def optimize(
        self,
        query: str,
        mode: Literal["auto", "lats", "mcts"] = "auto",
        ocr_text: Optional[str] = None,
        current_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute optimization based on mode.

        Args:
            query: 최적화할 질의
            mode: 최적화 모드 (auto, lats, mcts)
            ocr_text: OCR 텍스트 (LATS 상태 주입용)
            current_answer: 현재 답변 (LATS 상태 주입용)
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
            # 초기 상태에 query, ocr_text, current_answer 주입
            initial_state = SearchState(
                query=query,
                ocr_text=ocr_text,
                current_answer=current_answer,
            )

            result_node = await self.lats.run(initial_state=initial_state)

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
        """Heuristic for complexity detection.
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
