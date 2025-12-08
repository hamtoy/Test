"""관리자용 캐시 엔드포인트 (로컬/개인용, 인증 없음)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

from fastapi import APIRouter, HTTPException

from src.qa.rule_loader import (
    clear_global_rule_cache,
    get_global_cache_info,
)

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/admin", tags=["admin"])
P = ParamSpec("P")
R = TypeVar("R")


def admin_get(path: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper for router.get."""
    return cast("Callable[[Callable[P, R]], Callable[P, R]]", router.get(path))


def admin_post(path: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper for router.post."""
    return cast("Callable[[Callable[P, R]], Callable[P, R]]", router.post(path))


@admin_get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """전역 RuleLoader 캐시 통계 조회."""
    try:
        cache_info = get_global_cache_info()
        logger.info(
            "Admin cache stats requested: hits=%s misses=%s",
            cache_info["hits"],
            cache_info["misses"],
        )
        return {"cache": cache_info, "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get cache stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@admin_post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """전역 RuleLoader 캐시 초기화."""
    try:
        clear_global_rule_cache()
        logger.warning("Global rule cache cleared via admin endpoint")
        return {"message": "Global rule cache cleared", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to clear cache: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@admin_get("/cache/health")
async def cache_health() -> dict[str, Any]:
    """캐시 히트율 기반 헬스체크."""
    cache_info = get_global_cache_info()
    hit_rate = float(cache_info.get("hit_rate") or 0.0)
    status = "ok" if hit_rate >= 0.5 else "warning"
    message = (
        "Cache healthy"
        if status == "ok"
        else "Low cache hit rate - check query patterns or increase maxsize"
    )
    return {
        "status": status,
        "hit_rate": hit_rate,
        "message": message,
        "cache": cache_info,
    }


@admin_get("/cache/analytics")
async def get_cache_analytics() -> dict[str, Any]:
    """캐시 분석 데이터 조회 (hit rate, TTL 효율성, 메모리 사용량 등).

    Returns:
        Comprehensive cache analytics including real-time metrics
    """
    from src.caching.analytics import CacheAnalytics, get_unified_cache_report
    from src.web.cache import answer_cache

    try:
        # Create analytics instance for global answer cache
        analytics = CacheAnalytics()

        # Sync with answer_cache stats
        stats = answer_cache.get_stats()
        for _ in range(stats["hits"]):
            analytics.record_hit()
        for _ in range(stats["misses"]):
            analytics.record_miss()

        # Get unified report from all registered cache namespaces
        unified_report = get_unified_cache_report()

        summary = analytics.get_summary()
        summary["answer_cache"] = stats
        summary["namespaces"] = unified_report.get("namespaces", {})

        logger.info(
            "Cache analytics requested: hit_rate=%.2f%%, requests=%d",
            summary["realtime_hit_rate"],
            summary["total_requests"],
        )

        return {
            "success": True,
            "data": summary,
            "message": f"Hit rate: {summary['realtime_hit_rate']:.1f}%",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get cache analytics: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "캐시 분석 데이터 조회 실패",
        }


@admin_get("/metrics/realtime")
async def get_realtime_metrics() -> dict[str, Any]:
    """실시간 성능 메트릭 조회 (latency p50/p90/p99, 토큰, 비용).

    Returns:
        Real-time performance metrics aggregated over the last 60 minutes
    """
    from src.analytics.realtime_dashboard import get_dashboard

    try:
        dashboard = get_dashboard()
        summary = await dashboard.get_summary()

        logger.info(
            "Realtime metrics requested: total_requests=%d, endpoints=%d",
            summary.get("total_requests", 0),
            len(summary.get("endpoints", {})),
        )

        return {
            "success": True,
            "data": summary,
            "message": f"Total requests: {summary.get('total_requests', 0)}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get realtime metrics: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "실시간 메트릭 조회 실패",
        }


@admin_get("/system/suggestions")
async def get_system_suggestions() -> dict[str, Any]:
    """시스템 자가 개선 제안 조회 (품질/비용/레이턴시 트렌드 분석).

    Returns:
        Performance analysis and improvement suggestions
    """
    from src.features.self_improvement import SelfImprovingSystem

    try:
        system = SelfImprovingSystem()
        report = await system.analyze_and_suggest()

        issues_count = report.get("issues_found", 0)
        status = report.get("status", "analyzed")

        logger.info(
            "System suggestions requested: %d issues found",
            issues_count,
        )

        return {
            "success": True,
            "data": report,
            "message": f"{issues_count}개 개선 제안"
            if status != "insufficient_data"
            else "분석할 데이터 부족",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get system suggestions: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "시스템 분석 실패",
        }


@admin_get("/qa/suggest-next")
async def suggest_next_query_type(session: str = "[]") -> dict[str, Any]:
    """다음 질의 유형 추천 (현재 세션 기반).

    Args:
        session: JSON string of current session query types

    Returns:
        Recommended next query types
    """
    import json as json_module

    from src.features.autocomplete import SmartAutocomplete

    try:
        current_session = json_module.loads(session) if session else []

        # Get knowledge graph for autocomplete
        from .qa_common import get_cached_kg

        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": "Knowledge graph not available",
                "message": "Neo4j 연결 필요",
            }

        autocomplete = SmartAutocomplete(kg)  # type: ignore[arg-type]
        suggestions = autocomplete.suggest_next_query_type(current_session)

        logger.info(
            "Query type suggestions requested: %d suggestions",
            len(suggestions),
        )

        return {
            "success": True,
            "data": {"suggestions": suggestions},
            "message": f"{len(suggestions)}개 질의 유형 추천",
        }
    except json_module.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid session JSON",
            "message": "세션 데이터 형식 오류",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to suggest query types: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "질의 유형 추천 실패",
        }


@admin_post("/rules/promote")
async def promote_rules(days: int = 7) -> dict[str, Any]:
    """검수 로그 분석 후 규칙 승격 (자동 규칙 추출).

    Args:
        days: Number of days to analyze (default: 7)

    Returns:
        Extracted and promoted rules from review logs
    """
    from src.automation.promote_rules import run_promote_rules

    try:
        rules = run_promote_rules(days=days)

        logger.info(
            "Rules promotion completed: %d rules extracted",
            len(rules),
        )

        return {
            "success": True,
            "data": {
                "rules": rules,
                "count": len(rules),
                "analysis_days": days,
            },
            "message": f"{len(rules)}개 규칙 추출",
        }
    except EnvironmentError as env_err:
        logger.error("Environment error in rule promotion: %s", env_err)
        return {
            "success": False,
            "error": str(env_err),
            "message": "환경 설정 오류 (GEMINI_API_KEY 확인)",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to promote rules: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "규칙 승격 실패",
        }


@admin_get("/reports/weekly")
async def get_weekly_report() -> dict[str, Any]:
    """주간 사용 현황 리포트 조회 (세션, 비용, 캐시, 토큰).

    Returns:
        Weekly usage statistics
    """
    from src.analytics.dashboard import UsageDashboard

    try:
        dashboard = UsageDashboard()
        stats = dashboard.generate_weekly_report()

        if "error" in stats:
            return {
                "success": False,
                "error": stats["error"],
                "message": "리포트 데이터 없음",
            }

        logger.info(
            "Weekly report generated: sessions=%d, cost=$%.2f",
            stats.get("total_sessions", 0),
            stats.get("total_cost_usd", 0),
        )

        return {
            "success": True,
            "data": stats,
            "message": f"총 {stats.get('total_sessions', 0)} 세션, ${stats.get('total_cost_usd', 0):.2f}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate weekly report: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "주간 리포트 생성 실패",
        }


@admin_post("/qa/validate")
async def validate_qa_pair(
    question: str,
    answer: str,
    query_type: str = "explanation",
) -> dict[str, Any]:
    """QA 쌍 교차 검증 (일관성, 근거, 규칙 준수, 참신성).

    Args:
        question: 질문 텍스트
        answer: 답변 텍스트
        query_type: 질의 유형 (explanation, reasoning 등)

    Returns:
        Validation results with issues found
    """
    from src.analysis.cross_validation import CrossValidationSystem

    from .qa_common import get_cached_kg

    try:
        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": "Knowledge graph not available",
                "message": "Neo4j 연결 필요",
            }

        validator = CrossValidationSystem(kg)  # type: ignore[arg-type]
        result = validator.cross_validate_qa_pair(
            question=question,
            answer=answer,
            query_type=query_type,
            image_meta={},  # No image metadata for API validation
        )

        issues_count = sum(len(v) for k, v in result.items() if k.endswith("_issues"))

        logger.info(
            "QA validation completed: %d issues found",
            issues_count,
        )

        return {
            "success": True,
            "data": result,
            "message": f"{issues_count}개 이슈 발견" if issues_count else "검증 통과",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to validate QA pair: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "QA 검증 실패",
        }


@admin_get("/metrics/prometheus")
async def get_prometheus_metrics() -> dict[str, Any]:
    """Prometheus 형식 메트릭 조회.

    Returns:
        Prometheus metrics data
    """
    from src.monitoring.metrics import get_metrics

    try:
        metrics_bytes = get_metrics()
        metrics_text = metrics_bytes.decode("utf-8")

        logger.info("Prometheus metrics requested")

        return {
            "success": True,
            "data": {"metrics": metrics_text},
            "content_type": "text/plain",
            "message": "Prometheus 메트릭",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get prometheus metrics: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "메트릭 조회 실패",
        }


@admin_get("/analysis/topics")
async def extract_semantic_topics(top_k: int = 30) -> dict[str, Any]:
    """Neo4j Block에서 토픽 키워드 추출.

    Args:
        top_k: 상위 몇 개 키워드 반환 (기본: 30)

    Returns:
        Top keywords with frequencies
    """
    import os

    from neo4j import GraphDatabase

    from src.analysis.semantic import count_keywords, fetch_blocks

    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([neo4j_uri, neo4j_user, neo4j_password]):
        return {
            "success": False,
            "error": "Neo4j not available",
            "message": "Neo4j 연결 필요",
        }

    try:
        assert neo4j_uri and neo4j_user and neo4j_password  # type narrowing
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        blocks = fetch_blocks(driver)
        driver.close()

        if not blocks:
            return {
                "success": True,
                "data": {"keywords": [], "count": 0},
                "message": "분석할 블록 없음",
            }

        contents = [b["content"] for b in blocks if b.get("content")]
        keyword_counter = count_keywords(contents)
        keywords = keyword_counter.most_common(top_k)

        logger.info(
            "Semantic topics extracted: %d keywords from %d blocks",
            len(keywords),
            len(blocks),
        )

        return {
            "success": True,
            "data": {
                "keywords": [{"word": w, "freq": f} for w, f in keywords],
                "count": len(keywords),
                "blocks_analyzed": len(blocks),
            },
            "message": f"{len(keywords)}개 토픽 추출",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract semantic topics: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "토픽 추출 실패",
        }


@admin_get("/analysis/documents/compare")
async def compare_documents(limit: int = 10) -> dict[str, Any]:
    """Neo4j Page/Block 문서 구조 비교.

    Args:
        limit: 공통 콘텐츠 반환 개수 (기본: 10)

    Returns:
        Document structure comparison and common content
    """
    import os

    from neo4j import GraphDatabase

    from src.analysis.document_compare import compare_structure, find_common_content

    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([neo4j_uri, neo4j_user, neo4j_password]):
        return {
            "success": False,
            "error": "Neo4j not available",
            "message": "Neo4j 연결 필요",
        }

    try:
        assert neo4j_uri and neo4j_user and neo4j_password  # type narrowing
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        structures = compare_structure(driver)
        common_contents = find_common_content(driver, limit=limit)
        driver.close()

        logger.info(
            "Document comparison: %d pages, %d common contents",
            len(structures),
            len(common_contents),
        )

        return {
            "success": True,
            "data": {
                "structures": structures,
                "common_contents": [
                    {"content": c[:200], "pages": p} for c, p in common_contents
                ],
                "page_count": len(structures),
            },
            "message": f"{len(structures)}개 페이지 비교",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to compare documents: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "문서 비교 실패",
        }


@admin_post("/qa/route")
async def route_query(user_input: str) -> dict[str, Any]:
    """사용자 입력을 분석해 최적 질의 유형 자동 선택 (그래프 기반).

    Args:
        user_input: 사용자 질의 텍스트

    Returns:
        Chosen query type and routing decision
    """
    from src.routing.graph_router import GraphEnhancedRouter

    from .qa_common import get_cached_kg

    try:
        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": "Knowledge graph not available",
                "message": "Neo4j 연결 필요",
            }

        router = GraphEnhancedRouter(kg=kg)  # type: ignore[arg-type]

        # 간단 핸들러: 선택만 반환 (실제 생성은 별도 API에서)
        handlers: dict[str, Any] = {}

        result = router.route_and_generate(user_input, handlers)
        chosen = result.get("choice", "unknown")

        logger.info("Query routed: input='%s...' -> %s", user_input[:50], chosen)

        return {
            "success": True,
            "data": {
                "chosen_type": chosen,
                "user_input": user_input[:200],
            },
            "message": f"질의 유형: {chosen}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to route query: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "질의 라우팅 실패",
        }
