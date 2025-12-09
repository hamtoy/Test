# mypy: allow-untyped-decorators
"""QA 생성 엔드포인트."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import traceback
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential

from checks.detect_forbidden_patterns import find_formatting_violations, find_violations
from src.agent import GeminiAgent
from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    ESTIMATED_CACHE_HIT_TIME_SAVINGS,
    QA_BATCH_TYPES,
    QA_BATCH_TYPES_THREE,
    QA_CACHE_OCR_TRUNCATE_LENGTH,
    QA_GENERATION_OCR_TRUNCATE_LENGTH,
)
from src.config.exceptions import SafetyFilterError
from src.processing.example_selector import DynamicExampleSelector
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator, validate_constraints
from src.web.cache import answer_cache
from src.web.models import GenerateQARequest
from src.web.response import APIMetadata, build_response
from src.web.utils import QTYPE_MAP, load_ocr_text, postprocess_answer

from .qa_common import (
    _difficulty_hint,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator_class,
    get_cached_kg,
    logger,
)

router = APIRouter(prefix="/api", tags=["qa-generation"])


@router.get("/qa/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics (PHASE 2B: Performance monitoring).

    Returns:
        Cache metrics including hit rate, size, and performance impact
    """
    stats = answer_cache.get_stats()
    # Add estimated time saved (use ESTIMATED_CACHE_HIT_TIME_SAVINGS constant)
    time_saved_seconds = stats["hits"] * ESTIMATED_CACHE_HIT_TIME_SAVINGS
    stats["estimated_time_saved_seconds"] = time_saved_seconds
    stats["estimated_time_saved_minutes"] = round(time_saved_seconds / 60, 2)

    return {
        "success": True,
        "data": stats,
        "message": f"Cache hit rate: {stats['hit_rate_percent']:.1f}%",
    }


@router.post("/qa/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """Clear all cached answers (PHASE 2B: Cache management).

    Returns:
        Success message with number of entries cleared
    """
    size_before = answer_cache.get_stats()["cache_size"]
    await answer_cache.clear()

    return {
        "success": True,
        "data": {"entries_cleared": size_before},
        "message": f"Cleared {size_before} cache entries",
    }


@router.post("/qa/generate")
async def api_generate_qa(body: GenerateQARequest) -> dict[str, Any]:
    """QA 생성 (배치: 전체 설명 선행 후 병렬, 단일: 타입별 생성)."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text(_get_config())

    try:
        start = datetime.now()
        if body.mode in {"batch", "batch_three"}:
            # Wrap entire batch processing in timeout
            async def _process_batch() -> dict[str, Any]:
                results: list[dict[str, Any]] = []

                batch_types = body.batch_types or QA_BATCH_TYPES
                if body.mode == "batch_three" and body.batch_types is None:
                    batch_types = QA_BATCH_TYPES_THREE
                if not batch_types:
                    raise HTTPException(
                        status_code=400,
                        detail="batch_types이 비어 있습니다.",
                    )

                first_type = batch_types[0]
                first_query: str = ""

                # 1단계: global_explanation 순차 생성
                try:
                    first_pair = await asyncio.wait_for(
                        generate_single_qa_with_retry(
                            current_agent, ocr_text, first_type
                        ),
                        timeout=_get_config().qa_single_timeout,
                    )
                    results.append(first_pair)
                    first_query = first_pair.get("query", "")
                except Exception as exc:  # noqa: BLE001
                    logger.error("%s 생성 실패: %s", first_type, exc)
                    results.append(
                        {
                            "type": first_type,
                            "query": "생성 실패",
                            "answer": f"일시적 오류: {str(exc)[:100]}",
                        },
                    )

                # 2단계: 나머지 타입 2개씩 병렬 생성 (Rate Limit 방지용 1초 딜레이)
                remaining_types = batch_types[1:]
                previous_queries = [first_query] if first_query else []

                # 2개씩 묶어서 처리 (완전 병렬보다 안전, 완전 순차보다 빠름)
                for i in range(0, len(remaining_types), 2):
                    batch = remaining_types[i : i + 2]

                    # 첫 번째 배치가 아니면 딜레이 추가 (Rate Limit 방지)
                    if i > 0:
                        await asyncio.sleep(0.5)  # 1.0초 → 0.5초로 단축

                    logger.info("⏳ %s 타입 생성 시작", ", ".join(batch))

                    batch_results = await asyncio.gather(
                        *[
                            generate_single_qa_with_retry(
                                current_agent,
                                ocr_text,
                                qtype,
                                previous_queries=previous_queries
                                if previous_queries
                                else None,
                            )
                            for qtype in batch
                        ],
                        return_exceptions=True,
                    )

                    for j, pair in enumerate(batch_results):
                        qtype = batch[j]
                        if isinstance(pair, Exception):
                            import sys

                            tb_str = "".join(
                                traceback.format_exception(
                                    type(pair), pair, pair.__traceback__
                                )
                            )
                            sys.stderr.write(
                                f"\n[ERROR TRACEBACK] {qtype}:\n{tb_str}\n"
                            )
                            logger.error("%s 생성 실패:\n%s", qtype, tb_str)
                            results.append(
                                {
                                    "type": qtype,
                                    "query": "생성 실패",
                                    "answer": f"일시적 오류: {str(pair)[:100]}",
                                },
                            )
                        else:
                            results.append(cast("dict[str, Any]", pair))
                            pair_dict = cast("dict[str, Any]", pair)
                            if (
                                pair_dict.get("query")
                                and pair_dict.get("query") != "생성 실패"
                            ):
                                previous_queries.append(pair_dict.get("query", ""))

                duration = (datetime.now() - start).total_seconds()
                meta = APIMetadata(duration=duration)
                return cast(
                    "dict[str, Any]",
                    build_response(
                        {"mode": "batch", "pairs": results},
                        metadata=meta,
                        config=_get_config(),
                    ),
                )

            return await asyncio.wait_for(
                _process_batch(),
                timeout=_get_config().qa_batch_timeout,
            )

        if not body.qtype:
            raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
        pair = await asyncio.wait_for(
            generate_single_qa(current_agent, ocr_text, body.qtype),
            timeout=_get_config().qa_single_timeout,
        )
        duration = (datetime.now() - start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            "dict[str, Any]",
            build_response(
                {"mode": "single", "pair": pair},
                metadata=meta,
                config=_get_config(),
            ),
        )

    except asyncio.TimeoutError:
        timeout_msg = (
            f"생성 시간 초과 ({_get_config().qa_batch_timeout if body.mode in {'batch', 'batch_three'} else _get_config().qa_single_timeout}초). "
            "다시 시도해주세요."
        )
        raise HTTPException(status_code=504, detail=timeout_msg)
    except Exception as e:
        logger.error("QA 생성 실패: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"생성 실패: {e!s}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def generate_single_qa_with_retry(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: list[str] | None = None,
) -> dict[str, Any]:
    """재시도 로직이 있는 QA 생성 래퍼."""
    return await generate_single_qa(agent, ocr_text, qtype, previous_queries)


async def generate_single_qa(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: list[str] | None = None,
) -> dict[str, Any]:
    """단일 QA 생성 - 규칙 적용 보장 + 호출 최소화."""
    current_kg = _get_kg()
    current_pipeline = _get_pipeline()

    # Phase 2-1: Normalize query type using QTYPE_MAP
    normalized_qtype = QTYPE_MAP.get(qtype, "explanation")
    logger.info(
        "Query type '%s' normalized to '%s' for rule loading",
        qtype,
        normalized_qtype,
    )

    query_intent = None
    max_chars: int | None = None

    if qtype == "target_short":
        query_intent = "간단한 사실 확인 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의에서 다룬 내용과 겹치지 않도록 구체적 팩트(날짜, 수치, 명칭 등)를 질문하세요:
{prev_text}
"""
    elif qtype == "target_long":
        query_intent = "핵심 요점을 묻는 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의와 다른 관점/세부 항목을 묻는 질문을 생성하세요:
{prev_text}
"""
    elif qtype == "reasoning":
        query_intent = "추론/예측 질문"
    elif qtype == "global_explanation":
        query_intent = "전체 내용 설명 질문"

    # 중복/병렬 질문 방지 공통 지시
    single_focus_clause = """
[단일 포커스 필수]
- 한 가지 과업만 질문 (근거+전망처럼 두 항목을 동시에 묻지 말 것)
- '와/과/및/또는'으로 서로 다른 질문을 병렬 연결 금지
- 필요하면 한 항목만 묻도록 재작성
"""
    if query_intent:
        query_intent += single_focus_clause
    else:
        query_intent = single_focus_clause

    rule_loader = RuleLoader(current_kg)
    rules_list = rule_loader.get_rules_for_type(normalized_qtype, DEFAULT_ANSWER_RULES)
    query_constraints: list[dict[str, Any]] = []
    answer_constraints: list[dict[str, Any]] = []
    formatting_rules: list[str] = []
    unified_validator = UnifiedValidator(current_kg, current_pipeline)
    kg_wrapper: Any | None = get_cached_kg()

    if kg_wrapper is not None:
        try:
            # [Fix] Step 1: Enhanced type validation with detailed logging
            # Use normalized_qtype to ensure subtypes (e.g., target_short) get constraints from parent (target)
            constraints = kg_wrapper.get_constraints_for_query_type(normalized_qtype)

            if not isinstance(constraints, list):
                logger.error(
                    "🔴 Invalid constraints type from Neo4j: expected list, got %s. Value: %r",
                    type(constraints).__name__,
                    repr(constraints)[:100],
                )
                constraints = []

            # [Fix] Step 2: Validate each item is a dict with detailed logging
            valid_constraints = []
            invalid_items = []

            for c in constraints:
                if isinstance(c, dict):
                    valid_constraints.append(c)
                else:
                    invalid_items.append(
                        {"type": type(c).__name__, "value": repr(c)[:50]},
                    )

            if invalid_items:
                logger.error(
                    "🔴 Invalid constraint items dropped: %d/%d. Samples: %s",
                    len(invalid_items),
                    len(constraints),
                    str(invalid_items[:3])[:200],  # Limit log message size
                )

            # [Fix] Step 3: Safe category access with .get()
            query_constraints = [
                c for c in valid_constraints if c.get("category") in ["query", "both"]
            ]
            answer_constraints = [
                c for c in valid_constraints if c.get("category") in ["answer", "both"]
            ]

            # Success logging
            logger.info(
                "✅ Constraints loaded: query=%d, answer=%d",
                len(query_constraints),
                len(answer_constraints),
            )
            # [Fix] Step 4: Enhanced formatting rules validation
            try:
                fmt_rules = kg_wrapper.get_formatting_rules_for_query_type(
                    normalized_qtype,
                )

                # Type validation with detailed logging
                if not isinstance(fmt_rules, list):
                    logger.error(
                        "🔴 Invalid formatting rules type: expected list, got %s",
                        type(fmt_rules).__name__,
                    )
                    fmt_rules = []

                # Validate each rule is a dict
                valid_fmt_rules = []
                for fr in fmt_rules:
                    if isinstance(fr, dict):
                        desc = fr.get("description") or fr.get("text")
                        if desc:
                            formatting_rules.append(desc)
                            valid_fmt_rules.append(fr)
                    else:
                        logger.warning(
                            "Invalid formatting rule (not dict): %s",
                            type(fr).__name__,
                        )

                logger.info("✅ Formatting rules loaded: %d", len(formatting_rules))
            except Exception as e:  # noqa: BLE001
                logger.debug("서식 규칙 로드 실패: %s", e)

            logger.info(
                "%s 타입: 질의 제약 %s개, 답변 제약 %s개 조회",
                qtype,
                len(query_constraints),
                len(answer_constraints),
            )
        except Exception as e:
            logger.warning("규칙 조회 실패: %s", e)

    # 질의 중복/복합 방지용 공통 제약 추가
    query_constraints.append(
        {
            "description": "단일 과업만 묻기: '와/과/및/또는'으로 병렬 질문(두 가지 이상 요구) 금지",
            "priority": 100,
            "category": "query",
        },
    )

    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)
        logger.info("Neo4j 규칙 없음, 기본 규칙 사용")

    extra_instructions = "질의 유형에 맞게 작성하세요."
    length_constraint = ""
    if normalized_qtype == "reasoning":
        extra_instructions = """추론형 답변입니다.
[필수 구조 - 질의답변예시.txt 형식]
1. 첫 줄: **굵은 제목** (핵심 전망/결론을 한 문장으로)
2. 본문: 불릿 포인트(-)로 근거와 추론 나열
3. 마지막 문장: 종합적 결론

[예시 형식]
**고용 시장 전망 악화로 금리 인하 앞당겨질 가능성**
- 첫 번째 근거 설명
- 두 번째 근거 설명
- 결론적으로 ~할 것으로 전망됩니다.

[금지 사항]
- '근거', '추론 과정', '결론' 등 명시적 라벨 금지
- 불필요한 서론 금지 (바로 핵심으로)
- 장황한 설명 금지"""
        length_constraint = """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 최대 200단어, 3-5개 불릿 포인트의 간결한 추론이어야 합니다.
- 굵은 제목 1줄 + 불릿 포인트 3-5개
- 각 불릿은 1-2문장
- 최대 200단어 초과 금지
"""
    elif normalized_qtype == "explanation":
        # Few-Shot: Load examples from Neo4j for better length adherence
        fewshot_text = ""
        try:
            fewshot_examples: list[dict[str, Any]] = []
            if current_kg is not None:
                example_selector = DynamicExampleSelector(current_kg)
                fewshot_examples = example_selector.select_best_examples(
                    "explanation", {}, k=1
                )
            if fewshot_examples:
                ex = fewshot_examples[0]
                ex_text = ex.get("example", "")[:1500]  # Truncate if too long
                fewshot_text = f"""
[좋은 답변 예시 - 이 길이와 구조를 참고하세요]
{ex_text}
---
위 예시처럼 **충분한 길이와 구조**로 작성하세요.
"""
                logger.info("Few-Shot example loaded: %d chars", len(ex_text))
        except Exception as e:
            logger.debug("Few-shot loading failed: %s", e)

        extra_instructions = f"""설명형 답변입니다.
[필수 구조]
1. 첫 줄: **굵은 제목** (핵심 내용을 한 문장으로)
2. 도입: 1-2문장으로 전체 맥락 요약
3. 본문: 불릿 포인트(-)로 주요 요인 나열 (최소 5개)
4. 결론: 마지막 문장으로 종합

{fewshot_text}

[금지 사항]
- '서론', '본론', '결론' 등 라벨 금지
- 불필요한 반복, 장황한 수식어 금지"""

        # Dynamic length calculation (60-80% of OCR length)
        ocr_len = len(ocr_text)
        min_chars = int(ocr_len * 0.6)
        max_chars = int(ocr_len * 0.8)

        length_constraint = f"""
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 OCR 원문 길이({ocr_len}자)에 비례하여 **최소 {min_chars}자 ~ 최대 {max_chars}자** 분량입니다.
- 5-8개 문단으로 구성
- 굵은 제목 1줄 + 도입 1-2문장 + 불릿 5개 이상 + 결론
- 각 불릿은 1-2문장
- 핵심 포인트를 빠짐없이 다룰 것
❌ {min_chars}자 미만 = 실패 (반드시 길이 준수)
"""
    elif normalized_qtype == "target":
        if qtype == "target_short":
            extra_instructions = """
⚠️ 중요: 반드시 1-2문장만 작성. 3문장 이상 작성하면 실패입니다.
- 명확하고 간결한 사실 전달
- 불필요한 수식어 배제
- 구체적 수치나 데이터 포함
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
"""
            length_constraint = """
[CRITICAL - 길이 제약 ⚠️ 가장 중요]
1-2문장, 50-150자만 작성하세요.
❌ 3문장 이상 = 실패
❌ 150자 초과 = 실패
❌ 배경 설명 = 실패
❌ 볼드체(**) 사용 = 실패
✅ 핵심 사실만 1-2문장으로, 마크다운 없이 답변
"""
            rules_list = rules_list[:3]
        elif qtype == "target_long":
            extra_instructions = """
- OCR 원문의 특정 내용에 집중하여 서술
- 핵심 맥락과 함께 간결하게 답변
- 불필요한 배경 설명 최소화
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
"""
            length_constraint = """
[CRITICAL - 길이 제약]
200-400자, 3-4문장의 간결한 서술형 답변이어야 합니다.
- 정확히 3-4개 문장으로 구성
- 각 문장은 50-100자 정도
- 핵심 내용만 포함, 장황한 설명 금지
- 문단 구분 없이 하나의 문단으로 작성
❌ 볼드체(**) 사용 금지 - 마크다운 없이 평문으로 작성
"""
            rules_list = rules_list[:5]

    # PHASE 2B: Check cache before expensive operations to save ~6-12s
    # Use truncated OCR for cache key (QA_CACHE_OCR_TRUNCATE_LENGTH)
    cache_ocr_key = ocr_text[:QA_CACHE_OCR_TRUNCATE_LENGTH]

    try:
        # First, try to generate the query
        queries = await agent.generate_query(
            ocr_text,
            user_intent=query_intent,
            query_type=qtype,
            kg=kg_wrapper or current_kg,
            constraints=query_constraints,
        )
        if not queries:
            raise ValueError("질의 생성 실패")

        query = queries[0]

        # PHASE 2B: Enhanced cache logging for debugging
        cache_key_hash = hashlib.sha256(
            f"{query}|{cache_ocr_key}|{qtype}".encode(),
        ).hexdigest()[:16]
        logger.info(
            "Cache Key Generated - "
            "Query length: %d | "
            "OCR: %d | "
            "Type: %s | "
            "Key hash: %s",
            len(query),
            len(cache_ocr_key),
            qtype,
            cache_key_hash,
        )

        # PHASE 2B: Check cache after query generation
        cached_result = await answer_cache.get(query, cache_ocr_key, qtype)
        if cached_result is not None:
            cache_stats = answer_cache.get_stats()
            logger.info(
                "✅ CACHE HIT! Saved ~%d seconds. "
                "Query: %s... | "
                "Current cache size: %d | "
                "Hit rate: %.1f%%",
                ESTIMATED_CACHE_HIT_TIME_SAVINGS,
                query[:50],
                cache_stats["cache_size"],
                cache_stats["hit_rate_percent"],
            )
            return cast("dict[str, Any]", cached_result)

        cache_stats = answer_cache.get_stats()
        logger.info(
            "❌ CACHE MISS - Will generate new answer. "
            "Current cache size: %d | "
            "Hit rate: %.1f%%",
            cache_stats["cache_size"],
            cache_stats["hit_rate_percent"],
        )

        truncated_ocr = ocr_text[:QA_GENERATION_OCR_TRUNCATE_LENGTH]
        rules_in_answer = "\n".join(f"- {r}" for r in rules_list)
        formatting_text = ""
        if formatting_rules:
            formatting_text = "\n[서식 규칙 - 필수 준수]\n" + "\n".join(
                f"- {r}" for r in formatting_rules
            )

        # Add markdown usage policy based on qtype (Phase 1: IMPROVEMENTS.md)
        if normalized_qtype == "target":
            formatting_text += (
                "\n\n[마크다운 사용]\n"
                "평문으로만 작성하세요. "
                "마크다운(**bold**, *italic*, - 등)은 사용하지 마세요. "
                "(→ 후처리에서 모두 제거됩니다)"
            )
        elif normalized_qtype in {"explanation", "reasoning"}:
            formatting_text += (
                "\n\n[마크다운 사용 규칙 - 필수 준수]\n"
                "✅ 허용되는 마크다운:\n"
                "  - **bold**: 핵심 키워드 강조용 (예: **주요 포인트**)\n"
                "  - 1. 2. 3.: 순서가 있는 목록\n"
                "  - - 항목: 순서가 없는 불릿 포인트\n"
                "\n"
                "❌ 사용 금지 마크다운:\n"
                "  - *italic*: 가독성 저하 (절대 사용 금지)\n"
                "  - ### 제목: 불필요한 헤더 (절대 사용 금지)\n"
                "  - `코드`: 일반 QA에 불필요\n"
                "\n"
                "예시 (올바른 형식):\n"
                "**미-중 갈등 고조 및 투자 심리 위축**\n"
                "전일 한국 증시는 여러 요인이 복합적으로 작용...\n"
                "- 첫 번째 요인: 설명\n"
                "- 두 번째 요인: 설명\n"
            )

        constraints_text = ""
        if answer_constraints:

            def _priority_value(item: dict[str, Any]) -> float:
                val = item.get("priority")
                return float(val) if isinstance(val, (int, float)) else 0.0

            answer_constraints.sort(key=_priority_value, reverse=True)
            constraints_text = "\n".join(
                f"[우선순위 {c.get('priority', 0)}] {c.get('description', '')}"
                for c in answer_constraints
            )

            # Phase 3: Validate constraint conflicts (IMPROVEMENTS.md)
            # Extract max_length from length_constraint if present
            max_length_val: int | None = None
            if "50단어" in length_constraint:
                max_length_val = 50
            elif "100단어" in length_constraint:
                max_length_val = 100
            elif "200단어" in length_constraint:
                max_length_val = 200
            elif "300단어" in length_constraint:
                max_length_val = 300

            # Check for paragraph constraints in answer_constraints
            # Note: This is a heuristic parser for constraint descriptions.
            # Expected format: "X문단, 각 Y단어 이상" or similar
            min_per_para: int | None = None
            num_paras: int | None = None
            for constraint in answer_constraints:
                desc = constraint.get("description", "").lower()
                if "문단" in desc and "단어" in desc:
                    # Try to extract numbers from constraint description
                    numbers = re.findall(r"\d+", desc)
                    if len(numbers) >= 2:
                        # Heuristic: first number might be paragraph count, second might be words
                        try:
                            if "각" in desc or "당" in desc:
                                num_paras = int(numbers[0])
                                min_per_para = int(numbers[1])
                        except (ValueError, IndexError):
                            pass

            if max_length_val:
                is_valid, validation_msg = validate_constraints(
                    qtype=normalized_qtype,
                    max_length=max_length_val,
                    min_per_paragraph=min_per_para,
                    num_paragraphs=num_paras,
                )
                if not is_valid:
                    logger.warning(
                        "⚠️ 제약 충돌 감지: %s (qtype=%s)",
                        validation_msg,
                        normalized_qtype,
                    )

        difficulty_text = _difficulty_hint(ocr_text)
        evidence_clause = "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거가 되는 문장을 1개 포함하세요."

        # Phase 2: Add explicit priority hierarchy and conflict resolution (IMPROVEMENTS.md)
        markdown_rule = (
            "평문만 (마크다운 제거)"
            if normalized_qtype == "target"
            else "구조만 마크다운(제목/목록), 내용은 평문"
        )
        max_length_text = ""
        if "최대 50단어" in length_constraint:
            max_length_text = "50단어"
        elif "최대 100단어" in length_constraint:
            max_length_text = "100단어"
        elif "200단어" in length_constraint:
            max_length_text = "200단어"
        else:
            max_length_text = "[MAX_LENGTH]단어"

        priority_hierarchy = f"""
[PRIORITY HIERARCHY]
Priority 0 (CRITICAL):
- {normalized_qtype} 타입: {markdown_rule}

Priority 10 (HIGH):
- 최대 길이: {max_length_text} 이내
- 길이 제약 위반은 불가능

Priority 20 (MEDIUM):
- 구조화 형식: {formatting_text if formatting_text else "기본 서식"}

Priority 30 (LOW):
- 추가 지시: {extra_instructions}

[CONFLICT RESOLUTION]
만약 여러 제약이 충돌한다면:
→ Priority 0 > Priority 10 > Priority 20 > Priority 30

[REASONING BEFORE RESPONSE]
응답하기 전에 다음을 확인하세요:
1. 현재 qtype은 무엇인가? → 올바른 마크다운 규칙 확인 (Priority 0)
2. 길이 제약은 몇 단어인가? → {max_length_text} 이내 유지 (Priority 10)
3. 구조화 방식은? → formatting_text 규칙 적용 (Priority 20)
4. 추가 요청사항은? → extra_instructions 추가 처리 (Priority 30)
"""

        answer_prompt = f"""{priority_hierarchy}

{length_constraint}

{formatting_text}

[제약사항]
{constraints_text or rules_in_answer}

[질의]: {query}

[OCR 텍스트]
{truncated_ocr}

위 길이/형식 제약과 규칙을 엄격히 준수하여 한국어로 답변하세요.
{difficulty_text}
{evidence_clause}
{extra_instructions}"""

        draft_answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=answer_prompt,
            cached_content=None,
            query_type=normalized_qtype,
            kg=kg_wrapper or current_kg,
            constraints=answer_constraints,
            length_constraint=length_constraint,
        )
        if not draft_answer:
            raise SafetyFilterError("No text content in response.")

        # Enhanced logging for answer length debugging (Fix #3)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Answer length tracking - qtype=%s, OCR=%d chars, draft=%d chars",
                qtype,
                len(ocr_text),
                len(draft_answer),
            )

        # 통합 검증으로 수집할 위반/경고 (질의 포함하여 금지 패턴 검증 강화)
        val_result = unified_validator.validate_all(
            draft_answer,
            normalized_qtype,
            query,
        )
        all_issues: list[str] = []

        sentences = [
            s
            for s in draft_answer.replace("?", ".").replace("!", ".").split(".")
            if s.strip()
        ]
        sentence_count = len(sentences)
        # target_short만 문장 수 제한 (1-2문장), 나머지 타입은 검증 skip
        if qtype == "target_short" and sentence_count > 2:
            all_issues.append(f"1-2문장으로 축소 필요 (현재 {sentence_count}문장)")

        all_violations: list[str] = []
        if normalized_qtype == "reasoning" and (
            "요약문" in draft_answer or "요약" in draft_answer.splitlines()[0]
        ):
            all_violations.append("summary_header_not_allowed")

        # Explicit rule compliance check when KG is available (for tests/validation)
        if kg_wrapper is not None:
            try:
                validator_cls = _get_validator_class()
                validator = validator_cls(kg_wrapper)
                rule_check = validator._check_rule_compliance(
                    draft_answer,
                    normalized_qtype,
                )
                score = rule_check.get("score")
                score_val = score if isinstance(score, (int, float)) else 1.0
                if rule_check.get("violations") and score_val < 0.3:
                    all_violations.extend(rule_check.get("violations", []))
            except Exception:
                pass

        # 기존 탐지 + 통합 검증 병합
        violations = find_violations(draft_answer)
        if violations:
            for v in violations:
                v_type = v["type"]
                # NOTE: 시의성 표현은 인간 작업자가 최종 수정 예정이므로 검증 제외
                if v_type.startswith("error_pattern:시의성"):
                    continue
                if "temporal" in v_type.lower():
                    continue  # 시의성 관련 모든 패턴 제외
                all_violations.append(v_type)

        formatting_violations = find_formatting_violations(draft_answer)
        for fv in formatting_violations:
            if fv.get("severity") == "error":
                all_violations.append(fv["type"])
                logger.warning(
                    "서식 위반 감지: %s - '%s'",
                    fv.get("description", ""),
                    fv["match"],
                )

        if current_pipeline is not None:
            validation = current_pipeline.validate_output(
                normalized_qtype,
                draft_answer,
            )
            if not validation.get("valid", True):
                all_violations.extend(validation.get("violations", []))
            missing_rules = validation.get("missing_rules_hint", [])
            if missing_rules:
                logger.debug("누락 가능성 있는 규칙: %s", missing_rules)

        if val_result.has_errors():
            all_violations.extend(
                [v.get("type", "rule") for v in val_result.violations],
            )
        if val_result.warnings:
            all_issues.extend(val_result.warnings)

        # 시의성 관련 위반 필터링 (인간 작업자가 최종 수정 예정)
        all_violations = [
            v
            for v in all_violations
            if "시의성" not in v and "temporal" not in v.lower()
        ]

        if all_violations:
            all_issues.extend(all_violations[:3])

        if all_issues:
            combined_request = "; ".join(all_issues)
            logger.warning("검증 실패, 재생성 시도: %s", combined_request)
            try:
                rewritten = await agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=draft_answer,
                    edit_request=f"다음 사항 수정: {combined_request}",
                    cached_content=None,
                    constraints=answer_constraints,
                    length_constraint=length_constraint,
                )
                # 빈 응답이면 원본 유지
                if rewritten and rewritten.strip():
                    draft_answer = rewritten
                else:
                    logger.warning("재생성 빈 응답, 원본 답변 사용")
            except Exception as e:
                # 재생성 실패 시 원본 답변 사용 (Gemini API 일시 오류 대응)
                logger.warning("재생성 실패, 원본 답변 사용: %s", str(e)[:100])

        final_answer = postprocess_answer(draft_answer, qtype, max_length=max_chars)

        # Enhanced logging: track length changes through post-processing (Fix #3)
        if normalized_qtype == "explanation":
            logger.info(
                "Answer length - OCR: %d chars | Draft: %d chars | Final: %d chars | Query: %s",
                len(ocr_text),
                len(draft_answer),
                len(final_answer),
                query[:50],
            )

        # Validate answer length for explanation type
        if normalized_qtype == "explanation":
            answer_length = len(final_answer)
            # Use dynamic min_chars (60% of OCR length) instead of hardcoded value
            if answer_length < min_chars:
                logger.warning(
                    "⚠️ Answer too short for explanation type: "
                    "%d chars (expected %d+, OCR %d chars). "
                    "Query: %s",
                    answer_length,
                    min_chars,
                    len(ocr_text),
                    query[:50],
                )

        # PHASE 2B: Store result in cache for future requests
        result = {"type": qtype, "query": query, "answer": final_answer}
        await answer_cache.set(query, cache_ocr_key, qtype, result)
        logger.debug("Cached answer for query_type=%s", qtype)

        return result
    except Exception as e:
        logger.error("QA 생성 실패: %s", e)
        raise
