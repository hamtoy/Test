"""워크스페이스 워크플로우 실행기."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
)

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.qa.pipeline import IntegratedQAPipeline
    from src.qa.rag_system import QAKnowledgeGraph

# Lazy imports to avoid circular dependencies
from src.config.constants import DEFAULT_ANSWER_RULES
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator
from src.web.utils import QTYPE_MAP, postprocess_answer
from src.workflow.edit import edit_content

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
    changes: list[str]
    query_type: str


class WorkspaceExecutor:
    """워크스페이스 워크플로우 실행 엔진.

    기존 workspace.py의 복잡한 로직을 분리하여 테스트 가능하고 유지보수하기 쉽게 만듦.
    """

    def __init__(
        self,
        agent: GeminiAgent,
        kg: QAKnowledgeGraph | None,
        pipeline: IntegratedQAPipeline | None,
        config: AppConfig,
        edit_fn: Callable[..., Awaitable[str]] | None = None,
    ):
        """핵심 의존성을 주입해 실행기를 초기화."""
        self.agent = agent
        self.kg = kg
        self.pipeline = pipeline
        self.config = config
        self.edit_fn: Callable[..., Awaitable[str]] = edit_fn or edit_content

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
        changes: list[str] = ["OCR에서 전체 생성"]

        # 1. 질의 생성
        query_intent = self._get_query_intent(
            ctx.query_type,
            ctx.global_explanation_ref,
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
        changes: list[str] = ["기존 답변 기반 질의 생성"]

        query_intent = self._get_query_intent(
            ctx.query_type,
            ctx.global_explanation_ref,
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
        changes: list[str] = ["기존 질의 기반 답변 생성"]

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
        changes: list[str] = ["답변 재작성"]

        # 재작성 요청으로 답변 개선 (edit_fn 활용)
        answer = await self._apply_edit(
            target_text=ctx.answer,
            ctx=ctx,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
        )
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
        changes: list[str] = ["질의 수정 요청 반영"]

        # edit_content를 사용해 질의 수정
        edited_query = await self._apply_edit(
            target_text=ctx.query,
            ctx=ctx,
            edit_request=ctx.edit_request or "질의를 개선해주세요.",
        )

        query = edited_query or ctx.query

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 수정 완료")

        return WorkflowResult(
            workflow="edit_query",
            query=query,
            answer=ctx.answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_edit_answer(self, ctx: WorkflowContext) -> WorkflowResult:
        """답변 편집 워크플로우."""
        changes: list[str] = ["답변 수정 요청 반영"]

        answer = await self._apply_edit(
            target_text=ctx.answer,
            ctx=ctx,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
        )
        changes.append("답변 수정 완료")

        return WorkflowResult(
            workflow="edit_answer",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    async def _handle_edit_both(self, ctx: WorkflowContext) -> WorkflowResult:
        """질의와 답변 모두 편집 워크플로우."""
        changes: list[str] = ["질의와 답변 수정 요청 반영"]

        # 1. 답변 편집 (edit_fn 활용)
        answer = await self._apply_edit(
            target_text=ctx.answer,
            ctx=ctx,
            edit_request=ctx.edit_request or "답변을 개선해주세요.",
        )
        changes.append("답변 수정 완료")

        # 2. 질의 편집
        edited_query = await self._apply_edit(
            target_text=ctx.query,
            ctx=ctx,
            edit_request=ctx.edit_request or "질의를 개선해주세요.",
        )

        query = edited_query or ctx.query

        if ctx.query_type == "target_short":
            query = self._shorten_query(query)

        changes.append("질의 조정 완료")

        return WorkflowResult(
            workflow="edit_both",
            query=query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )

    # ===== 헬퍼 메서드 =====
    async def _apply_edit(
        self,
        *,
        target_text: str,
        ctx: WorkflowContext,
        edit_request: str,
    ) -> str:
        """edit_fn 호출 후 필요 시 fallback."""
        try:
            edited = await self.edit_fn(
                agent=self.agent,
                answer=target_text,
                ocr_text=ctx.ocr_text,
                query=ctx.query,
                edit_request=edit_request,
                kg=self.kg,
                cache=None,
            )
        except TypeError:
            # edit_content가 Mock agent와 함께 호출될 때를 위한 fallback
            if hasattr(self.agent, "rewrite_best_answer"):
                edited = await self.agent.rewrite_best_answer(
                    ocr_text=ctx.ocr_text,
                    best_answer=target_text,
                    edit_request=edit_request,
                    cached_content=None,
                    query_type=ctx.query_type,
                )
            else:
                raise

        # Return edited content without post-processing to preserve user's edits
        return edited

    def _get_query_intent(self, query_type: str, global_ref: str) -> str:
        """쿼리 타입별 인텐트 생성 (Jinja2 템플릿 사용)."""
        template = self.jinja_env.get_template("prompts/workspace/query_intent.jinja2")
        return str(
            template.render(
                query_type=query_type,
                global_explanation_ref=global_ref,
            ),
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
        normalized_qtype = QTYPE_MAP.get(ctx.query_type, "explanation")
        rules_list = []
        extra_rules = []

        if self.kg is not None:
            rule_loader = RuleLoader(self.kg)
            rules_list = rule_loader.get_rules_for_type(
                normalized_qtype,
                DEFAULT_ANSWER_RULES,
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

        # Length constraint based on query type (with OCR length for explanation)
        length_constraint = self._get_length_constraint(
            ctx.query_type, len(ctx.ocr_text)
        )

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
        hint = self._get_difficulty_hint(ctx.ocr_text, ctx.query_type)
        if ctx.edit_request:
            hint += f"\n[사용자 추가 요청]\n{ctx.edit_request}"

        # Evidence clause
        evidence_clause = (
            "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거 문장을 1개 포함하세요."
        )

        # Render prompt using Jinja2 template
        template = self.jinja_env.get_template(
            "prompts/workspace/answer_generation.jinja2",
        )
        prompt = template.render(
            query=query,
            ocr_text=ctx.ocr_text,
            rules_list=rules_list[:5]
            if ctx.query_type == "target_short"
            else rules_list,
            extra_rules=extra_rules[:5] if extra_rules else [],
            length_constraint=length_constraint,
            dedup_section=dedup_section,
            difficulty_hint=hint,
            evidence_clause=evidence_clause,
        )

        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=prompt,
            cached_content=None,
            query_type=normalized_qtype,
        )

        # 후처리 - workspace operations don't apply OCR-based length limits
        # Just clean up markdown and ensure basic formatting
        answer = postprocess_answer(answer, ctx.query_type, max_length=None)

        # Validate answer and optionally rewrite if validation fails
        answer = await self._validate_and_fix_answer(
            answer,
            ctx,
            normalized_qtype,
            length_constraint,
        )

        return answer

    async def _validate_and_fix_answer(
        self,
        answer: str,
        ctx: WorkflowContext,
        normalized_qtype: str,
        length_constraint: str,
    ) -> str:
        """Validate answer and optionally rewrite if validation fails."""
        validator = UnifiedValidator(self.kg, self.pipeline)
        # Pass query to validate forbidden patterns in questions as well
        val_result = validator.validate_all(answer, normalized_qtype, ctx.query)

        # If there are errors or warnings, attempt to rewrite
        if val_result.has_errors() or val_result.warnings:
            edit_request_parts: list[str] = []

            if val_result.has_errors():
                edit_request_parts.append(val_result.get_error_summary())

            if val_result.warnings:
                edit_request_parts.extend(val_result.warnings[:2])

            edit_request = "; ".join(
                [p for p in edit_request_parts if p] or ["형식/규칙 위반 수정"],
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
                answer = postprocess_answer(
                    answer, ctx.query_type, max_length=None
                )  # 재작성 시에는 max_length 강제 적용은 보류하거나 필요 시 추가
                logger.info("검증 기반 재작성 완료")
            except Exception as exc:
                logger.debug("재작성 실패, 기존 답변 유지: %s", exc)

        return answer

    def _get_length_constraint(self, query_type: str, ocr_len: int = 0) -> str:
        """Get length constraint based on query type.

        Args:
            query_type: 질의 유형
            ocr_len: OCR 텍스트 길이 (explanation용 동적 계산)
        """
        constraints = {
            "target_short": """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 정확히 1-2문장, 50-150자의 간결한 답변이어야 합니다.
- 정확히 1-2문장으로 제한
- 최대 150자 초과 금지
- 단순 사실만 전달, 배경 설명 불필요
- 명확하고 직접적인 표현만 사용
- 불필요한 상세 설명은 배제
""",
            "target_long": """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 최소 300-600자 분량의 상세한 답변이어야 합니다.
- 정확히 5-6개 문장으로 구성
- 각 문장은 25-50자 정도의 적절한 길이
- 관련 배경 정보와 예시 포함
- 최소 300자 이상의 충분한 설명
- 단순 나열이 아닌 논리적 흐름 유지
""",
            "reasoning": """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 최대 200단어, 3-4문장 이내의 간결한 추론이어야 합니다.
- 정확히 3-4개 문장으로 구성
- 최대 200단어 초과 금지
- 불필요한 서론/결론 배제하고 핵심 추론만 제시
- "제시된 증거는..." 같은 반복적 문구 제외
""",
        }

        # explanation: OCR 60-80% 동적 계산
        if query_type in ("explanation", "global_explanation"):
            if ocr_len > 0:
                min_chars = int(ocr_len * 0.6)
                max_chars = int(ocr_len * 0.8)
                return f"답변은 OCR 길이에 비례하여 {min_chars}-{max_chars}자 범위로 작성하세요. 불릿·마크다운 사용 가능."
            return "답변은 OCR 길이의 60-80% 수준으로 작성하세요."

        return constraints.get(query_type, "")

    def _get_difficulty_hint(self, ocr_text: str, query_type: str) -> str:
        """Get difficulty hint based on OCR text length and query type."""
        # 상세 답변이 필요한 타입은 길이를 이유로 짧게 줄이지 않음
        if query_type in ("target_long", "explanation", "global_explanation"):
            return "관련 내용을 상세하고 충실하게 서술하세요."

        length = len(ocr_text)
        if length > 2000:
            return "본문이 길어 핵심 숫자·근거만 간결히 답하세요."
        return "불필요한 서론 없이 핵심을 짧게 서술하세요."

    def _strip_output_tags(self, text: str) -> str:
        """Remove <output> tags from text.
        
        Args:
            text: Text potentially containing <output> or <OUTPUT> tags
            
        Returns:
            Text with output tags removed
        """
        # Remove <output>...</output> tags (case-insensitive)
        result = re.sub(r'<output>(.*?)</output>', r'\1', text, flags=re.IGNORECASE | re.DOTALL)
        # Also handle self-closing or incomplete tags
        result = re.sub(r'</?output>', '', result, flags=re.IGNORECASE)
        return result
