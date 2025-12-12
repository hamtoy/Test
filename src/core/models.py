import logging
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# 모듈 전체에서 재사용
logger = logging.getLogger("GeminiWorkflow")

# CandidateID는 A, B, C만 허용
CandidateID = Literal["A", "B", "C"]


class EvaluationItem(BaseModel):
    """Represents a single candidate evaluation result."""

    candidate_id: CandidateID  # Literal로 강제
    score: int
    reason: str


class EvaluationResultSchema(BaseModel):
    """Schema for structured evaluation results from the LLM."""

    best_candidate: CandidateID = Field(
        description="The key of the best candidate (e.g., 'A', 'B', 'C').",
    )
    evaluations: list[EvaluationItem] = Field(
        description="List of evaluations for each candidate.",
    )

    @model_validator(mode="after")
    def validate_best_candidate(self) -> "EvaluationResultSchema":
        """LLM이 주장한 best_candidate와 실제 점수가 일치하는지 검증.

        불일치 시 자동 수정하여 downstream 에러를 방지합니다 (Hallucination Detection).
        """
        if self.evaluations:
            # 실제 최고 점수 후보 찾기
            actual_best = max(self.evaluations, key=lambda x: x.score)

            # LLM의 주장과 실제가 다르면 경고 후 수정
            if self.best_candidate != actual_best.candidate_id:
                logger.warning(
                    f"⚠️ LLM Hallucination Detected: "
                    f"Claimed '{self.best_candidate}' but scores show '{actual_best.candidate_id}' "
                    f"(score: {actual_best.score}). Auto-correcting...",
                )
                self.best_candidate = actual_best.candidate_id

        return self

    def get_best_candidate_id(self) -> CandidateID:
        """점수가 가장 높은 후보의 ID를 반환합니다.

        best_candidate 필드를 우선 사용하고, 없으면 evaluations에서 최고점을 찾습니다.

        Returns:
            최고 점수 후보의 ID (A, B, C 중 하나)
        """
        # best_candidate is always set (Literal type guarantees "A", "B", or "C")
        return self.best_candidate


class StructuredAnswerItem(BaseModel):
    """항목 하나의 구조."""

    label: str = Field(description="항목명")
    text: str = Field(description="1-2문장 설명")


class StructuredSection(BaseModel):
    """섹션 하나의 구조."""

    title: str = Field(description="소제목 (서론/본론/결론 같은 라벨 금지)")
    items: list[StructuredAnswerItem] = Field(description="항목 목록")


class StructuredAnswerSchema(BaseModel):
    """구조화된 답변 스키마 - 설명/추론 타입용."""

    intro: str = Field(description="1-2문장 도입")
    sections: list[StructuredSection] = Field(description="섹션 목록")
    conclusion: str = Field(description="마지막 1-2문장")


class QueryResult(BaseModel):
    """LLM이 생성한 질의 리스트를 구조화하여 받기 위한 모델."""

    queries: list[str] = Field(
        description="Generated list of strategic search queries based on the user intent and OCR text.",
    )


class WorkflowResult(BaseModel):
    """워크플로우의 최종 결과를 담는 객체 (DTO)."""

    turn_id: int = Field(description="Iteration turn number")
    query: str
    evaluation: EvaluationResultSchema | None
    best_answer: str
    rewritten_answer: str
    cost: float = 0.0
    final_output: str | None = None
    success: bool = False
    error_message: str | None = None
