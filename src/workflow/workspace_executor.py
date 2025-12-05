"""워크스페이스 워크플로우 실행기."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.qa.pipeline import IntegratedQAPipeline
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """워크플로우 타입."""

    FULL_GENERATION = "full_generation"
    QUERY_GENERATION = "query_generation"
    ANSWER_GENERATION = "answer_generation"
    REWRITE = "rewrite"
    EDIT_QUERY = "edit_query"
    EDIT_ANSWER = "edit_answer"
    EDIT_BOTH = "edit_both"


@dataclass
class WorkflowContext:
    """워크플로우 실행 컨텍스트."""

    query: str
    answer: str
    ocr_text: str
    query_type: str
    edit_request: str
    global_explanation_ref: str
    use_lats: bool


@dataclass
class WorkflowResult:
    """워크플로우 실행 결과."""

    workflow: str
    query: str
    answer: str
    changes: List[str]
    query_type: str


class WorkspaceExecutor:
    """워크스페이스 워크플로우 실행 엔진.

    기존 workspace.py의 복잡한 로직을 분리하여 테스트 가능하고 유지보수하기 쉽게 만듦.
    """

    def __init__(
        self,
        agent: GeminiAgent,
        kg: Optional[QAKnowledgeGraph],
        pipeline: Optional[IntegratedQAPipeline],
        config: AppConfig,
    ):
        """핵심 의존성을 주입해 실행기를 초기화."""
        self.agent = agent
        self.kg = kg
        self.pipeline = pipeline
        self.config = config

    async def execute(
        self,
        workflow: WorkflowType,
        context: WorkflowContext,
    ) -> WorkflowResult:
        """워크플로우 실행."""
        logger.info(
            "Executing workflow: %s (qtype=%s)",
            workflow.value,
            context.query_type,
        )

        handlers = {
            WorkflowType.FULL_GENERATION: self._handle_full_generation,
            WorkflowType.QUERY_GENERATION: self._handle_query_generation,
            WorkflowType.ANSWER_GENERATION: self._handle_answer_generation,
            WorkflowType.REWRITE: self._handle_rewrite,
            WorkflowType.EDIT_QUERY: self._handle_edit_query,
            WorkflowType.EDIT_ANSWER: self._handle_edit_answer,
            WorkflowType.EDIT_BOTH: self._handle_edit_both,
        }

        handler = handlers.get(workflow)
        if handler is None:
            raise ValueError(f"Unknown workflow: {workflow}")

        return await handler(context)

    # ===== 워크플로우 핸들러 =====

    async def _handle_full_generation(self, ctx: WorkflowContext) -> WorkflowResult:
        """전체 생성 워크플로우."""
        changes: List[str] = ["OCR에서 전체 생성"]

        # 1. 질의 생성
        query_intent = self._get_query_intent(
            ctx.query_type, ctx.global_explanation_ref
        )
        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )

        query = queries[0] if queries else "질문 생성 실패"

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 생성 완료")

        # 2. 답변 생성 (현재는 단순화된 버전)
        answer = await self._generate_answer(ctx, query)
        changes.append("답변 생성 완료")

        return WorkflowResult(
            workflow="full_generation",
            query=query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_query_generation(self, ctx: WorkflowContext) -> WorkflowResult:
        """질의 생성 워크플로우."""
        changes: List[str] = ["기존 답변 기반 질의 생성"]

        query_intent = self._get_query_intent(
            ctx.query_type, ctx.global_explanation_ref
        )
        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )

        query = queries[0] if queries else "질문 생성 실패"

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 생성 완료")

        return WorkflowResult(
            workflow="query_generation",
            query=query,
            answer=ctx.answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_answer_generation(self, ctx: WorkflowContext) -> WorkflowResult:
        """답변 생성 워크플로우."""
        changes: List[str] = ["기존 질의 기반 답변 생성"]

        answer = await self._generate_answer(ctx, ctx.query)
        changes.append("답변 생성 완료")

        return WorkflowResult(
            workflow="answer_generation",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_rewrite(self, ctx: WorkflowContext) -> WorkflowResult:
        """재작성 워크플로우."""
        changes: List[str] = ["답변 재작성"]

        # 재작성 요청으로 답변 개선
        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=ctx.answer,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
            cached_content=None,
            query_type=ctx.query_type,
        )

        answer = self._strip_output_tags(answer)
        changes.append("재작성 완료")

        return WorkflowResult(
            workflow="rewrite",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_edit_query(self, ctx: WorkflowContext) -> WorkflowResult:
        """질의 편집 워크플로우."""
        changes: List[str] = ["질의 편집"]

        # 질의 재생성
        query_intent = self._get_query_intent(
            ctx.query_type, ctx.global_explanation_ref
        )
        if ctx.edit_request:
            query_intent = f"{query_intent}\n\n추가 요청: {ctx.edit_request}"

        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )

        query = queries[0] if queries else ctx.query

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 편집 완료")

        return WorkflowResult(
            workflow="edit_query",
            query=query,
            answer=ctx.answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_edit_answer(self, ctx: WorkflowContext) -> WorkflowResult:
        """답변 편집 워크플로우."""
        changes: List[str] = ["답변 편집"]

        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=ctx.answer,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
            cached_content=None,
            query_type=ctx.query_type,
        )

        answer = self._strip_output_tags(answer)
        changes.append("답변 편집 완료")

        return WorkflowResult(
            workflow="edit_answer",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_edit_both(self, ctx: WorkflowContext) -> WorkflowResult:
        """질의와 답변 모두 편집 워크플로우."""
        changes: List[str] = ["질의와 답변 편집"]

        # 1. 질의 편집
        query_intent = self._get_query_intent(
            ctx.query_type, ctx.global_explanation_ref
        )
        if ctx.edit_request:
            query_intent = f"{query_intent}\n\n추가 요청: {ctx.edit_request}"

        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )

        query = queries[0] if queries else ctx.query

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 편집 완료")

        # 2. 답변 편집
        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=ctx.answer,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
            cached_content=None,
            query_type=ctx.query_type,
        )

        answer = self._strip_output_tags(answer)
        changes.append("답변 편집 완료")

        return WorkflowResult(
            workflow="edit_both",
            query=query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    # ===== 헬퍼 메서드 =====

    def _get_query_intent(self, query_type: str, global_ref: str) -> str:
        """쿼리 타입별 인텐트 생성."""
        intents = {
            "target_short": "간단한 사실 확인 질문",
            "target_long": "핵심 요점을 묻는 질문",
            "reasoning": "추론/예측 질문",
            "global_explanation": "전체 내용 설명 질문",
        }

        base_intent = intents.get(query_type, "전체 내용 설명 질문")

        # 중복 방지 추가
        if global_ref and query_type in {"target_short", "target_long"}:
            base_intent += f"""

[중복 방지 필수]
다음 전체 설명문에서 이미 다룬 내용과 중복되지 않는 새로운 세부 사실/수치를 질문하세요:
---
{global_ref[:500]}
---"""

        return base_intent

    def _shorten_query(self, text: str) -> str:
        """타겟 단답용 질의 압축."""
        clean = re.sub(r"\s+", " ", text or "").strip()
        parts = re.split(r"[?.!]\s*", clean)
        candidate = parts[0] if parts and parts[0] else clean
        words = candidate.split()
        if len(words) > 20:
            candidate = " ".join(words[:20])
        return candidate.strip()

    async def _generate_answer(self, ctx: WorkflowContext, query: str) -> str:
        """답변 생성 (공통 로직)."""
        # 단순화된 프롬프트 생성
        prompt = f"""[질의]
{query}

[OCR 텍스트]
{ctx.ocr_text[:2000]}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=prompt,
            cached_content=None,
            query_type=ctx.query_type,
        )

        # 후처리
        answer = self._strip_output_tags(answer)
        answer = self._postprocess_answer(answer, ctx.query_type)

        return answer

    def _strip_output_tags(self, text: str) -> str:
        """<output> 태그 제거."""
        text = re.sub(r"<output>|</output>", "", text, flags=re.IGNORECASE)
        return text.strip()

    def _postprocess_answer(self, answer: str, query_type: str) -> str:
        """답변 후처리."""
        # query_type에 따른 추가 처리 (필요시)
        return answer.strip()
