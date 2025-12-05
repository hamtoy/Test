"""Workspace 공통 유틸리티 및 헬퍼 함수."""
# mypy: ignore-errors

from __future__ import annotations

import contextlib
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Final, Optional

from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import (
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
)
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.service_registry import get_registry

if TYPE_CHECKING:
    from src.features.lats import SearchNode

logger = logging.getLogger(__name__)

# Backward compatibility: keep global variables for modules that import them
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None

# 검증 재시도 최대 횟수
MAX_REWRITE_ATTEMPTS = 3


@dataclass(frozen=True)
class AnswerQualityWeights:
    """실전용 LATS 답변 품질 가중치."""

    base_score: float = 0.4  # 기본 40점
    length_weight: float = 0.10  # 적절한 길이 10점
    number_match_weight: float = 0.25  # 숫자 정확도 25점 (핵심!)
    no_forbidden_weight: float = 0.15  # 형식 위반 없음 15점
    constraint_weight: float = 0.10  # Neo4j 규칙 준수 10점

    # 길이 기준 (실전 최적화)
    min_length: int = 15  # 너무 짧은 답변 배제
    max_length: int = 1200  # 너무 긴 답변 배제 (실제 사용자 선호)

    # 숫자 일치 기준 강화
    min_number_overlap: int = 1  # 최소 1개 숫자 일치 필수


LATS_WEIGHTS_PRESETS: Final[dict[str, AnswerQualityWeights]] = {
    # 기본 설명형 질문
    "explanation": AnswerQualityWeights(
        number_match_weight=0.25,  # 숫자 정확도 중시
        length_weight=0.15,  # 적당한 길이
    ),
    # 표/차트 데이터 추출
    "table_summary": AnswerQualityWeights(
        number_match_weight=0.35,  # 숫자 정확도 최우선
        length_weight=0.10,
        base_score=0.35,
    ),
    # 비교/분석 질문
    "comparison": AnswerQualityWeights(
        number_match_weight=0.20,
        length_weight=0.20,  # 비교는 길이가 길어도 OK
        constraint_weight=0.15,  # Neo4j 비교 규칙 중시
    ),
    # 트렌드/시계열 분석
    "trend_analysis": AnswerQualityWeights(
        number_match_weight=0.30,  # 연도/수치 정확도 필수
        constraint_weight=0.20,  # 시계열 규칙 중시
    ),
    # 엄격한 형식 요구 질문
    "strict": AnswerQualityWeights(
        no_forbidden_weight=0.25,  # 형식 오류 0容
        number_match_weight=0.25,
        base_score=0.30,
    ),
}

DEFAULT_LATS_WEIGHTS = LATS_WEIGHTS_PRESETS["explanation"]

_difficulty_levels = {
    "long": "본문이 길어 핵심 숫자·근거만 간결히 답하세요.",
    "medium": "불필요한 서론 없이 핵심을 짧게 서술하세요.",
}


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    kg_ref: Optional[QAKnowledgeGraph],
    qa_pipeline: Optional[IntegratedQAPipeline] = None,
) -> None:
    """주요 의존성 주입."""
    global _config, agent, kg, pipeline
    _config = config
    agent = gemini_agent
    kg = kg_ref
    pipeline = qa_pipeline
    # Reset validator in registry
    with contextlib.suppress(RuntimeError):
        get_registry().register_validator(None)


def _get_agent() -> Optional[GeminiAgent]:
    """Registry에서 agent 가져오기. 실패 시 api 모듈 fallback."""
    try:
        return get_registry().agent
    except RuntimeError:
        # api 모듈 fallback (테스트 호환성)
        try:
            from src.web import api as api_module

            if getattr(api_module, "agent", None) is not None:
                return api_module.agent
        except Exception:
            pass
        if agent is not None:
            return agent
        logger.error("Agent 초기화 안 됨")
        return None


def _get_kg() -> Optional[QAKnowledgeGraph]:
    """Registry에서 KG 가져오기. 실패 시 api 모듈 fallback."""
    try:
        return get_registry().kg
    except RuntimeError:
        try:
            from src.web import api as api_module

            if getattr(api_module, "kg", None) is not None:
                return api_module.kg
        except Exception:
            pass
        return kg


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    """Registry에서 pipeline 가져오기. 실패 시 api 모듈 fallback."""
    try:
        return get_registry().pipeline
    except RuntimeError:
        try:
            from src.web import api as api_module

            if getattr(api_module, "pipeline", None) is not None:
                return api_module.pipeline
        except Exception:
            pass
        return pipeline


def _get_config() -> AppConfig:
    """Registry에서 config 가져오기. 실패 시 api 모듈 fallback."""
    try:
        cfg = get_registry().config
    except RuntimeError:
        cfg = None
        try:
            from src.web import api as api_module

            cfg = getattr(api_module, "config", None)
        except Exception:
            pass
        if cfg is None:
            cfg = _config
        if cfg is None:
            logger.warning("Registry 초기화 안 됨, 기본 Config 사용")
            cfg = AppConfig()

    # 테스트 호환성: timeout 필드가 정수인지 확인 (MagicMock 방어)
    timeout_defaults = [
        ("workspace_timeout", WORKSPACE_GENERATION_TIMEOUT),
        ("workspace_unified_timeout", WORKSPACE_UNIFIED_TIMEOUT),
        ("qa_single_timeout", QA_SINGLE_GENERATION_TIMEOUT),
        ("qa_batch_timeout", QA_BATCH_GENERATION_TIMEOUT),
    ]
    try:
        for name, default in timeout_defaults:
            val = getattr(cfg, name, None)
            if not isinstance(val, int):
                setattr(cfg, name, default)
    except Exception:
        # MagicMock이나 다른 예외 발생 시 모든 기본값 설정
        for name, default in timeout_defaults:
            setattr(cfg, name, default)

    return cfg


def _get_validator() -> Optional[CrossValidationSystem]:
    """Registry에서 validator 가져오기. 없으면 생성."""
    try:
        registry = get_registry()

        # 캐시된 validator 반환
        if registry.validator is not None:
            return registry.validator

        # kg 없으면 None
        kg_instance = registry.kg
        if kg_instance is None:
            return None

        # 새로 생성 및 등록
        validator = CrossValidationSystem(kg_instance)
        registry.register_validator(validator)
        return validator

    except Exception as exc:
        logger.debug("Validator 초기화 실패: %s", exc)
        return None


def _difficulty_hint(ocr_text: str) -> str:
    """OCR 텍스트 길이에 따른 난이도 힌트 생성."""
    length = len(ocr_text)
    if length > 4000:
        return _difficulty_levels["long"]
    if length > 2000:
        return _difficulty_levels["long"]
    return _difficulty_levels["medium"]


async def _evaluate_answer_quality(
    answer: str,
    query: str,
    ocr_text: str,
    rules_list: list[str],
    weights: AnswerQualityWeights,
) -> float:
    """답변 품질 평가 (LATS용 헬퍼 함수)."""
    from checks.detect_forbidden_patterns import find_violations

    score = weights.base_score

    # 길이 평가
    answer_len = len(answer)
    if weights.min_length <= answer_len <= weights.max_length:
        score += weights.length_weight

    # 숫자 일치도 평가
    ocr_numbers = set(re.findall(r"\d+", ocr_text))
    answer_numbers = set(re.findall(r"\d+", answer))
    num_overlap = len(ocr_numbers & answer_numbers)
    if num_overlap >= weights.min_number_overlap:
        ratio = min(num_overlap / max(len(ocr_numbers), 1), 1.0)
        score += weights.number_match_weight * ratio

    # 형식 위반 검사
    violations = find_violations(answer)
    if not violations:
        score += weights.no_forbidden_weight

    # Neo4j 규칙 준수 (간단한 키워드 매칭)
    if rules_list and any(rule_keyword in answer for rule_keyword in ["기준", "근거", "정확"]):
        score += weights.constraint_weight

    return min(score, 1.0)


async def _lats_evaluate_answer(node: "SearchNode") -> float:
    """LATS 노드의 답변 품질 평가."""
    # This is a placeholder - actual implementation would use the node's context
    return 0.5
