from typing import List, Optional, Literal
import logging
from pydantic import BaseModel, Field, model_validator

# [Module-Level Logger] 모듈 전체에서 재사용
logger = logging.getLogger("GeminiWorkflow")

# [Strict Typing] CandidateID는 A, B, C만 허용
CandidateID = Literal["A", "B", "C"]

class EvaluationItem(BaseModel):
    candidate_id: CandidateID  # [Type Safety] Literal로 강제
    score: int
    reason: str

class EvaluationResultSchema(BaseModel):
    best_candidate: CandidateID = Field(description="The key of the best candidate (e.g., 'A', 'B', 'C').")
    evaluations: List[EvaluationItem] = Field(description="List of evaluations for each candidate.")

    @model_validator(mode='after')
    def validate_best_candidate(self):
        """
        [Hallucination Detection] LLM이 주장한 best_candidate와 실제 점수가 일치하는지 검증
        불일치 시 자동 수정하여 downstream 에러 방지
        """
        if self.evaluations:
            # 실제 최고 점수 후보 찾기
            actual_best = max(self.evaluations, key=lambda x: x.score)
            
            # LLM의 주장과 실제가 다르면 경고 후 수정
            if self.best_candidate != actual_best.candidate_id:
                logger.warning(
                    f"⚠️ LLM Hallucination Detected: "
                    f"Claimed '{self.best_candidate}' but scores show '{actual_best.candidate_id}' "
                    f"(score: {actual_best.score}). Auto-correcting..."
                )
                self.best_candidate = actual_best.candidate_id
        
        return self

    def get_best_candidate_id(self) -> CandidateID:
        """
        [Domain Logic] 점수가 가장 높은 후보의 ID를 반환합니다.
        best_candidate 필드를 우선 사용하고, 없으면 evaluations에서 최고점을 찾습니다.
        """
        # [Simplified] Literal 타입이 보장하므로 A/B/C 체크 불필요
        if self.best_candidate:
            return self.best_candidate
        
        # evaluations에서 최고점 찾기
        if not self.evaluations:
            return "A"  # 기본값

        # 점수 내림차순 정렬
        sorted_evals = sorted(self.evaluations, key=lambda x: x.score, reverse=True)
        return sorted_evals[0].candidate_id

class QueryResult(BaseModel):
    """
    [Structured Output] LLM이 생성한 질의 리스트를 구조화하여 받기 위한 모델
    """
    queries: List[str] = Field(
        description="Generated list of strategic search queries based on the user intent and OCR text."
    )

class WorkflowResult(BaseModel):
    """
    [Data Transfer Object] 워크플로우의 최종 결과를 담는 객체
    """
    turn_id: int = Field(description="Iteration turn number")
    query: str
    evaluation: Optional[EvaluationResultSchema]
    best_answer: str
    rewritten_answer: str
    cost: float = 0.0
    final_output: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
