# mypy: allow-untyped-decorators
"""QA 생성 및 평가 엔드포인트.

This module provides FastAPI endpoints for QA pair generation and evaluation:
- QA pair generation with Neo4j rule integration
- External answer evaluation
- Batch and single QA generation
- Quality validation and cross-validation

## Endpoints
- POST /qa/generate - Generate QA pairs from OCR text
- POST /eval/external - Evaluate external answers

## Structure
**Imports and Setup** (lines 1-40): Module imports and router initialization
**Dependency Management** (lines 41-214): Dependency injection and helper functions
**QA Generation** (lines 215-659): `/qa/generate` endpoint (batch and single)
**Answer Evaluation** (lines 660-end): `/eval/external` endpoint

Note: This is a large file. Consider future refactoring into:
  - qa_generation.py (QA pair generation logic)
  - qa_evaluation.py (Answer evaluation logic)
  - qa_batch.py (Batch processing logic)
  - qa_helpers.py (Shared utilities)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast


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

logger = logging.getLogger(__name__)

# Router defined in sub-modules

_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None

_kg_cache: Optional["_CachedKG"] = None
_kg_cache_timestamp: Optional[datetime] = None
_CACHE_TTL = timedelta(minutes=5)


class _CachedKG:
    """Lightweight KG wrapper with memoization."""

    def __init__(self, base: QAKnowledgeGraph) -> None:
        self._base = base
        self._constraints: dict[str, list[Dict[str, Any]]] = {}
        self._formatting_text: dict[str, str] = {}
        self._formatting_rules: dict[str, List[Dict[str, Any]]] = {}
        self._rules: dict[tuple[str, int], list[str]] = {}

    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        if query_type in self._constraints:
            return self._constraints[query_type]
        data = self._base.get_constraints_for_query_type(query_type)
        # Validate that data is a list before caching
        if not isinstance(data, list):
            logger.warning(
                "Invalid constraints data type from KG: expected list, got %s",
                type(data).__name__,
            )
            data = []
        self._constraints[query_type] = data
        return data

    def get_formatting_rules(self, template_type: str) -> str:
        if template_type in self._formatting_text:
            return self._formatting_text[template_type]
        text = self._base.get_formatting_rules(template_type)
        self._formatting_text[template_type] = text
        return text

    def get_formatting_rules_for_query_type(
        self, query_type: str
    ) -> List[Dict[str, Any]]:
        if query_type in self._formatting_rules:
            return self._formatting_rules[query_type]
        rules = self._base.get_formatting_rules_for_query_type(query_type)
        # Validate that rules is a list before caching
        if not isinstance(rules, list):
            logger.warning(
                "Invalid formatting rules data type from KG: expected list, got %s",
                type(rules).__name__,
            )
            rules = []
        self._formatting_rules[query_type] = rules
        return rules

    def find_relevant_rules(self, query: str, k: int = 10) -> List[str]:
        key = (query[:500], k)
        if key in self._rules:
            return self._rules[key]
        data = self._base.find_relevant_rules(query, k=k)
        self._rules[key] = data
        return data

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    qa_pipeline: Optional[IntegratedQAPipeline],
    kg_ref: Optional[QAKnowledgeGraph],
) -> None:
    """주요 의존성 주입."""
    global _config, agent, pipeline, kg
    _config = config
    agent = gemini_agent
    pipeline = qa_pipeline
    kg = kg_ref


def _get_agent() -> Optional[GeminiAgent]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "agent", None) is not None:
            return api_module.agent
    except Exception:
        pass
    return agent


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "pipeline", None) is not None:
            return api_module.pipeline
    except Exception:
        pass
    return pipeline


def _get_kg() -> Optional[QAKnowledgeGraph]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "kg", None) is not None:
            return api_module.kg
    except Exception:
        pass
    return kg


def _get_config() -> AppConfig:
    try:
        from src.web import api as api_module

        cfg_raw = getattr(api_module, "config", None) or _config
        if cfg_raw is not None:
            cfg = cast(AppConfig, cfg_raw)
            # Ensure numeric timeouts even when patched with MagicMock
            for name, default in [
                ("qa_single_timeout", QA_SINGLE_GENERATION_TIMEOUT),
                ("qa_batch_timeout", QA_BATCH_GENERATION_TIMEOUT),
                ("workspace_timeout", WORKSPACE_GENERATION_TIMEOUT),
                ("workspace_unified_timeout", WORKSPACE_UNIFIED_TIMEOUT),
            ]:
                try:
                    value = int(getattr(cfg, name, default))
                except Exception:
                    value = default
                setattr(cfg, name, value)
            try:
                cfg.enable_standard_response = bool(
                    getattr(cfg, "enable_standard_response", False)
                )
                cfg.enable_lats = bool(getattr(cfg, "enable_lats", False))
            except Exception:
                cfg.enable_standard_response = False
                cfg.enable_lats = False
            return cfg
    except Exception:
        if _config is not None:
            return _config
    try:
        from src.web import dependencies

        return dependencies.get_config()
    except Exception:
        return AppConfig()


def _get_validator_class() -> type[CrossValidationSystem] | Any:
    """테스트에서 패치한 CrossValidationSystem을 우선 사용."""
    try:
        from src.web import api as api_module

        return getattr(api_module, "CrossValidationSystem", CrossValidationSystem)
    except Exception:
        return CrossValidationSystem


def _difficulty_hint(ocr_text: str) -> str:
    length = len(ocr_text)
    if length > 4000:
        return "본문이 매우 길어요. 숫자·고유명사 중심으로 2-3문장 이내로 답하세요."
    if length > 2000:
        return "본문이 길어 핵심만 압축해 답하세요. 숫자·고유명사만 그대로 사용하세요."
    return "필요 이상의 부연 없이 핵심 숫자·근거 1문장을 포함해 간결히 답하세요."


def get_cached_kg() -> Optional["_CachedKG"]:
    """Return a cached KG wrapper valid for 5 minutes."""
    global _kg_cache, _kg_cache_timestamp
    current_kg = _get_kg()
    if current_kg is None:
        return None
    now = datetime.now()
    if _kg_cache and _kg_cache_timestamp and now - _kg_cache_timestamp < _CACHE_TTL:
        return _kg_cache
    _kg_cache = _CachedKG(current_kg)
    _kg_cache_timestamp = now
    return _kg_cache
