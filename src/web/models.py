"""API 요청/응답 모델"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GenerateQARequest(BaseModel):
    """QA 생성 요청"""

    mode: Literal["batch", "single"] = Field(
        ..., description="batch: 4타입 일괄, single: 단일 타입"
    )
    qtype: Optional[
        Literal["global_explanation", "reasoning", "target_short", "target_long"]
    ] = Field(None, description="mode=single일 때 필수")


class QAPair(BaseModel):
    """QA 쌍"""

    type: str
    query: str
    answer: str


class GenerateQAResponse(BaseModel):
    """QA 생성 응답"""

    mode: Literal["batch", "single"]
    pairs: Optional[List[QAPair]] = None  # batch
    pair: Optional[QAPair] = None  # single


class EvalExternalRequest(BaseModel):
    """외부 답변 평가 요청"""

    query: str = Field(..., description="질의 내용")
    answers: List[str] = Field(..., min_length=3, max_length=3, description="답변 3개")


class EvalResult(BaseModel):
    """평가 결과"""

    answer_id: str
    score: int
    feedback: str


class EvalExternalResponse(BaseModel):
    """외부 답변 평가 응답"""

    results: List[EvalResult]
    best: str


class WorkspaceRequest(BaseModel):
    """워크스페이스 요청"""

    mode: Literal["inspect", "edit"] = Field(
        ..., description="inspect: 검수, edit: 자유 수정"
    )
    query: Optional[str] = Field("", description="질의 (선택)")
    answer: str = Field(..., description="검수/수정할 답변")
    edit_request: Optional[str] = Field("", description="edit 모드일 때 수정 요청")
    inspector_comment: Optional[str] = Field(
        "", description="검수자 코멘트 (모든 모드에서 선택적으로 입력 가능)"
    )


class WorkspaceResponse(BaseModel):
    """워크스페이스 응답"""

    mode: Literal["inspect", "edit"]
    result: Dict[str, Any]


class MultimodalResponse(BaseModel):
    """이미지 분석 응답"""

    filename: str
    metadata: Dict[str, Any]
