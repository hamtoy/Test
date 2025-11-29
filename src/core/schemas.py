"""입력/출력 데이터 검증 스키마

Pydantic을 사용하여 입력 데이터의 유효성을 검증하고
오류를 조기에 차단합니다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class OCRInput(BaseModel):
    """OCR 텍스트 입력 검증"""

    text: str = Field(..., min_length=10, max_length=50000)
    language: Literal["ko", "en"] = "ko"

    @field_validator("text")
    @classmethod
    def check_text_quality(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("OCR 텍스트가 비어있습니다")

        # 특수문자만 있는 경우
        alnum_count = sum(1 for c in v if c.isalnum())
        if alnum_count < 5:
            raise ValueError("유효한 텍스트가 부족합니다")

        return v


class CandidateAnswer(BaseModel):
    """후보 답변 검증"""

    id: Literal["A", "B", "C"]
    content: str = Field(..., min_length=10, max_length=10000)


class EvaluationRequest(BaseModel):
    """평가 요청 검증"""

    query: str = Field(..., min_length=5, max_length=1000)
    candidates: list[CandidateAnswer] = Field(..., min_length=2, max_length=3)

    @field_validator("candidates")
    @classmethod
    def check_unique_ids(cls, v: list[CandidateAnswer]) -> list[CandidateAnswer]:
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("후보 ID가 중복됩니다")
        return v


class QAGenerationRequest(BaseModel):
    """QA 생성 요청 검증"""

    mode: Literal["batch", "single"]
    qtype: (
        Literal["global_explanation", "reasoning", "target_short", "target_long"] | None
    ) = None

    @field_validator("qtype")
    @classmethod
    def check_qtype_for_single(
        cls,
        v: str | None,
        info: object,
    ) -> str | None:
        # Pydantic v2에서는 info.data로 접근
        data = getattr(info, "data", {})
        if data.get("mode") == "single" and not v:
            raise ValueError("single 모드에서는 qtype 필수")
        return v


__all__ = [
    "OCRInput",
    "CandidateAnswer",
    "EvaluationRequest",
    "QAGenerationRequest",
]
