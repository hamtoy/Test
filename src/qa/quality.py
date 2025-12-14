"""Integrated Quality Enhancement System module.

Orchestrates all quality improvement features in a single pipeline:
image analysis, complexity adjustment, example selection, context augmentation,
LLM generation, self-correction, constraint compliance, and cross-validation.
"""

from __future__ import annotations

from typing import Any

from src.analysis.cross_validation import CrossValidationSystem
from src.features.autocomplete import SmartAutocomplete
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.features.multimodal import MultimodalUnderstanding
from src.features.self_correcting import SelfCorrectingQAChain
from src.infra.constraints import RealTimeConstraintEnforcer
from src.llm.gemini import GeminiModelClient
from src.processing.context_augmentation import AdvancedContextAugmentation
from src.processing.example_selector import DynamicExampleSelector
from src.qa.rag_system import QAKnowledgeGraph


class IntegratedQualitySystem:
    """모든 품질 향상 기능을 통합한 파이프라인.

    확장된 파이프라인:
    이미지분석 → 복잡도분석 → 예시선택 → 컨텍스트증강 → LLM생성
    → 자기교정 → 제약준수검사 → 실시간제약적용 → 크로스검증
    """

    def __init__(
        self,
        neo4j_uri: str,
        user: str,
        password: str,
        gemini_key: str | None = None,
    ):
        """Initialize the integrated quality system.

        Args:
            neo4j_uri: Neo4j database URI.
            user: Neo4j username.
            password: Neo4j password.
            gemini_key: Optional Gemini API key.
        """
        self.kg = QAKnowledgeGraph(neo4j_uri, user, password)
        self.augmenter = AdvancedContextAugmentation(
            neo4j_uri,
            user,
            password,
            gemini_key,
        )
        self.enforcer = RealTimeConstraintEnforcer(self.kg)
        self.adjuster = AdaptiveDifficultyAdjuster(self.kg)
        self.validator = CrossValidationSystem(self.kg)
        self.example_selector = DynamicExampleSelector(self.kg)
        self.multimodal = MultimodalUnderstanding(self.kg)
        self.llm = GeminiModelClient()
        # 새로 추가된 컴포넌트
        self.self_corrector = SelfCorrectingQAChain(self.kg, self.llm)
        self.autocomplete = SmartAutocomplete(self.kg)

    async def generate_qa_with_all_enhancements(
        self,
        image_path: str,
        query_type: str,
        enable_self_correction: bool = True,
    ) -> dict[str, Any]:
        """모든 품질 보강 기능을 적용한 QA 생성 플로우.

        확장된 파이프라인으로 자기교정, 제약 준수 검사, 실시간 제약 적용을 포함합니다.

        Args:
            image_path: 분석할 이미지 파일 경로
            query_type: 질의 유형 (예: "explanation", "summary")
            enable_self_correction: 자기 교정 기능 활성화 여부 (기본값: True)

        Returns:
            다음 키를 포함하는 딕셔너리:
            - output (str): 생성된 QA 답변 텍스트
            - validation (Dict): 크로스 검증 결과
            - metadata (Dict): 메타데이터
            - constraint_check (Dict): 제약 준수 검사 결과
            - self_correction (Dict | None): 자기 교정 결과 (활성화된 경우)
        """
        # 1. 이미지 분석
        image_meta = await self.multimodal.analyze_image_deep(image_path)

        # 2. 복잡도 분석 및 조정
        complexity = self.adjuster.analyze_image_complexity(image_meta)
        adjustments = self.adjuster.adjust_query_requirements(complexity, query_type)

        # 3. 최적 예시 선택
        examples = self.example_selector.select_best_examples(
            query_type,
            image_meta,
            k=3,
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

        # 6. 자기 교정 (선택적)
        self_correction_result: dict[str, Any] | None = None
        if enable_self_correction:
            self_correction_result = self.self_corrector.generate_with_self_correction(
                query_type=query_type,
                context={
                    "image_meta": image_meta,
                    "initial_draft": generated_output,
                },
            )
            # 교정된 출력으로 대체
            generated_output = self_correction_result.get("output", generated_output)

        # 7. 제약 준수 검사 (SmartAutocomplete)
        constraint_check = self.autocomplete.suggest_constraint_compliance(
            draft_output=generated_output,
            query_type=query_type,
        )

        # 8. 실시간 제약 검증 (RealTimeConstraintEnforcer)
        enforcement_result = self.enforcer.validate_complete_output(
            output=generated_output,
            query_type=query_type,
        )
        # 제약 위반이 없으면 그대로 사용
        final_output = generated_output

        # 9. 크로스 검증
        validation = self.validator.cross_validate_qa_pair(
            question="(auto-generated)",
            answer=final_output,
            query_type=query_type,
            image_meta=image_meta,
        )

        return {
            "output": final_output,
            "validation": validation,
            "metadata": {
                "complexity": complexity,
                "adjustments": adjustments,
                "examples_used": examples,
            },
            "constraint_check": constraint_check,
            "self_correction": self_correction_result,
            "enforcement": enforcement_result,
        }


__all__ = [
    "AdaptiveDifficultyAdjuster",
    "AdvancedContextAugmentation",
    "CrossValidationSystem",
    "DynamicExampleSelector",
    "GeminiModelClient",
    "IntegratedQualitySystem",
    "MultimodalUnderstanding",
    "QAKnowledgeGraph",
    "RealTimeConstraintEnforcer",
    "SelfCorrectingQAChain",
    "SmartAutocomplete",
]
