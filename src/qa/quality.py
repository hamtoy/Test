from __future__ import annotations

from typing import Any, Dict, Optional

from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.processing.context_augmentation import AdvancedContextAugmentation
from src.analysis.cross_validation import CrossValidationSystem
from src.processing.example_selector import DynamicExampleSelector
from src.features.multimodal import MultimodalUnderstanding
from src.qa.rag_system import QAKnowledgeGraph
from src.infra.constraints import RealTimeConstraintEnforcer
from src.llm.gemini import GeminiModelClient


class IntegratedQualitySystem:
    """모든 품질 향상 기능을 통합한 파이프라인."""

    def __init__(
        self,
        neo4j_uri: str,
        user: str,
        password: str,
        gemini_key: Optional[str] = None,
    ):
        self.kg = QAKnowledgeGraph(neo4j_uri, user, password)
        self.augmenter = AdvancedContextAugmentation(
            neo4j_uri, user, password, gemini_key
        )
        self.enforcer = RealTimeConstraintEnforcer(self.kg)
        self.adjuster = AdaptiveDifficultyAdjuster(self.kg)
        self.validator = CrossValidationSystem(self.kg)
        self.example_selector = DynamicExampleSelector(self.kg)
        self.multimodal = MultimodalUnderstanding(self.kg)
        self.llm = GeminiModelClient()

    def generate_qa_with_all_enhancements(
        self, image_path: str, query_type: str
    ) -> Dict[str, Any]:
        """모든 품질 보강 기능을 적용한 QA 생성 플로우.

        GeminiModelClient를 통해 실제 LLM을 호출하여 답변을 생성합니다.

        Args:
            image_path: 분석할 이미지 파일 경로
            query_type: 질의 유형 (예: "explanation", "summary")

        Returns:
            다음 키를 포함하는 딕셔너리:
            - output (str): 생성된 QA 답변 텍스트
            - validation (Dict): 크로스 검증 결과
            - metadata (Dict): 메타데이터, 다음 포함:
                - complexity (Dict): 이미지 복잡도 분석 결과
                - adjustments (Dict): 난이도 조정 정보
                - examples_used (List): 사용된 예시 리스트
        """
        # 1. 이미지 분석
        image_meta = self.multimodal.analyze_image_deep(image_path)

        # 2. 복잡도 분석 및 조정
        complexity = self.adjuster.analyze_image_complexity(image_meta)
        adjustments = self.adjuster.adjust_query_requirements(complexity, query_type)

        # 3. 최적 예시 선택
        examples = self.example_selector.select_best_examples(
            query_type, image_meta, k=3
        )

        # 4. 컨텍스트 증강
        augmented_prompt = self.augmenter.generate_with_augmentation(
            user_query=f"Generate {query_type} for image",
            query_type=query_type,
            base_context={
                "image_meta": image_meta,
                "adjustments": adjustments,
                "examples": examples,
            },
        )

        # 5. Gemini LLM 생성
        generated_output = self.llm.generate(augmented_prompt, role="generator")

        # 6. 크로스 검증
        validation = self.validator.cross_validate_qa_pair(
            question="(auto-generated)",  # 실제 질문을 여기에 넣어야 함
            answer=generated_output,
            query_type=query_type,
            image_meta=image_meta,
        )

        return {
            "output": generated_output,
            "validation": validation,
            "metadata": {
                "complexity": complexity,
                "adjustments": adjustments,
                "examples_used": examples,
            },
        }


__all__ = [
    "QAKnowledgeGraph",
    "AdvancedContextAugmentation",
    "RealTimeConstraintEnforcer",
    "AdaptiveDifficultyAdjuster",
    "CrossValidationSystem",
    "DynamicExampleSelector",
    "MultimodalUnderstanding",
    "GeminiModelClient",
    "IntegratedQualitySystem",
]
