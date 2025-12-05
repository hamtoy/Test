"""워크스페이스 워크플로우 실행기."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.qa.pipeline import IntegratedQAPipeline
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# Get repository root for template loading
REPO_ROOT = Path(__file__).parent.parent.parent


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
        
        # Jinja2 environment for prompt templates
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(REPO_ROOT / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

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
        """쿼리 타입별 인텐트 생성 (Jinja2 템플릿 사용)."""
        template = self.jinja_env.get_template("prompts/workspace/query_intent.jinja2")
        return template.render(
            query_type=query_type,
            global_explanation_ref=global_ref,
        )

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
        """답변 생성 (공통 로직 - Jinja2 템플릿 사용)."""
        # Get rules from KG if available
        from src.config.constants import DEFAULT_ANSWER_RULES
        from src.qa.rule_loader import RuleLoader
        from src.web.utils import QTYPE_MAP
        
        normalized_qtype = QTYPE_MAP.get(ctx.query_type, "explanation")
        rules_list = []
        extra_rules = []
        
        if self.kg is not None:
            rule_loader = RuleLoader(self.kg)
            rules_list = rule_loader.get_rules_for_type(
                normalized_qtype, DEFAULT_ANSWER_RULES
            )
            
            # Get additional rules from KG
            try:
                kg_rules = self.kg.get_rules_for_query_type(normalized_qtype)
                for r in kg_rules:
                    txt = r.get("text")
                    if txt:
                        extra_rules.append(txt)
            except Exception as exc:
                logger.debug("Rule 로드 실패: %s", exc)
        else:
            rules_list = DEFAULT_ANSWER_RULES
        
        # Length constraint based on query type
        length_constraint = self._get_length_constraint(ctx.query_type)
        
        # Deduplication section
        dedup_section = ""
        if ctx.global_explanation_ref:
            dedup_section = f"""[중복 금지]
다음 전체 설명문에 이미 나온 표현/숫자를 그대로 복사하지 말고, 필요한 경우 다른 문장으로 요약하세요.
전체 설명문에는 없지만 OCR 텍스트에만 등장하는 수치·사실은 꼭 포함하세요:
---
{ctx.global_explanation_ref[:500]}
---"""
        
        # Difficulty hint
        difficulty_hint = self._get_difficulty_hint(ctx.ocr_text)
        
        # Evidence clause
        evidence_clause = "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거 문장을 1개 포함하세요."
        
        # Render prompt using Jinja2 template
        template = self.jinja_env.get_template("prompts/workspace/answer_generation.jinja2")
        prompt = template.render(
            query=query,
            ocr_text=ctx.ocr_text,
            rules_list=rules_list[:5] if ctx.query_type == "target_short" else rules_list,
            extra_rules=extra_rules[:5] if extra_rules else [],
            length_constraint=length_constraint,
            dedup_section=dedup_section,
            difficulty_hint=difficulty_hint,
            evidence_clause=evidence_clause,
        )

        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=prompt,
            cached_content=None,
            query_type=normalized_qtype,
        )

        # 후처리
        answer = self._strip_output_tags(answer)
        answer = self._postprocess_answer(answer, ctx.query_type)
        
        # Phase 4: Validation layer integration
        answer = await self._validate_and_fix_answer(
            answer, ctx, normalized_qtype, length_constraint
        )

        return answer
    
    async def _validate_and_fix_answer(
        self, answer: str, ctx: WorkflowContext, normalized_qtype: str, length_constraint: str
    ) -> str:
        """Validate answer and optionally rewrite if validation fails (Phase 4)."""
        from src.qa.validator import UnifiedValidator
        
        validator = UnifiedValidator(self.kg, self.pipeline)
        val_result = validator.validate_all(answer, normalized_qtype)
        
        # If there are errors or warnings, attempt to rewrite
        if val_result.has_errors() or val_result.warnings:
            edit_request_parts: List[str] = []
            
            if val_result.has_errors():
                edit_request_parts.append(val_result.get_error_summary())
            
            if val_result.warnings:
                edit_request_parts.extend(val_result.warnings[:2])
            
            edit_request = "; ".join(
                [p for p in edit_request_parts if p] or ["형식/규칙 위반 수정"]
            )
            
            try:
                logger.info("답변 검증 실패, 재작성 시도: %s", edit_request)
                answer = await self.agent.rewrite_best_answer(
                    ocr_text=ctx.ocr_text,
                    best_answer=answer,
                    edit_request=edit_request,
                    cached_content=None,
                    length_constraint=length_constraint,
                )
                answer = self._strip_output_tags(answer)
                answer = self._postprocess_answer(answer, ctx.query_type)
                logger.info("검증 기반 재작성 완료")
            except Exception as exc:
                logger.debug("재작성 실패, 기존 답변 유지: %s", exc)
        
        return answer
    
    def _get_length_constraint(self, query_type: str) -> str:
        """Get length constraint based on query type."""
        if query_type == "target_short":
            return "답변은 불릿·마크다운(볼드/기울임) 없이 한 문장으로, 최대 50단어 이내로 작성하세요."
        elif query_type == "target_long":
            return "답변은 불릿·마크다운(볼드/기울임) 없이 3-4문장, 최대 100단어 이내로 작성하세요."
        elif query_type == "reasoning":
            return "불릿·마크다운(볼드/기울임) 없이 한 단락으로 간결하게 추론을 제시하세요."
        return ""
    
    def _get_difficulty_hint(self, ocr_text: str) -> str:
        """Get difficulty hint based on OCR text length."""
        length = len(ocr_text)
        if length > 2000:
            return "본문이 길어 핵심 숫자·근거만 간결히 답하세요."
        return "불필요한 서론 없이 핵심을 짧게 서술하세요."

    def _strip_output_tags(self, text: str) -> str:
        """<output> 태그 제거."""
        text = re.sub(r"<output>|</output>", "", text, flags=re.IGNORECASE)
        return text.strip()

    def _postprocess_answer(self, answer: str, query_type: str) -> str:
        """답변 후처리."""
        # Sanitize output
        answer = self._sanitize_output(answer)
        return answer.strip()
    
    def _sanitize_output(self, text: str) -> str:
        """불릿/마크다운/여분 공백을 제거해 일관된 문장만 남긴다."""
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"[_]{1,2}(.*?)[_]{1,2}", r"\1", text)
        text = text.replace("*", "")
        text = re.sub(r"^[\-\u2022]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text
