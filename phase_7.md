요청하신 마크다운 문서의 포맷을 수정했습니다.
주요 수정 사항은 다음과 같습니다.

1.  **코드 블록 언어 지정**: `python`, `bash`, `text` 등을 명시하여 문법 강조가 올바르게 작동하도록 했습니다.
2.  **ASCII 다이어그램 보존**: 텍스트로 된 다이어그램이나 박스가 깨지지 않도록 `text` 블록으로 지정했습니다.
3.  **들여쓰기 및 구문 정리**: 코드 가독성을 위해 들여쓰기를 정돈했습니다.

아래 내용을 그대로 복사해서 사용하시면 됩니다.

***

```markdown
# Phase 7: 캐싱 개선 - 구현 가이드 (최종판)

## 목표

Neo4j 쿼리 반복 호출을 줄여 성능을 향상시킵니다.
- RuleLoader의 규칙 조회 메모이제이션
- 빈번한 Neo4j 쿼리 캐싱
- LRU 캐시로 메모리 관리

## 현재 문제점

```python
# src/qa/rule_loader.py (현재)
class RuleLoader:
    def get_rules_for_type(self, query_type: str, defaults: list) -> list[str]:
        if not self.kg:
            return defaults
        
        try:
            # 매번 Neo4j 쿼리 실행 ❌
            kg_rules = self.kg.get_rules_for_query_type(query_type)
            return [r.get("text") for r in kg_rules if r.get("text")]
        except Exception:
            return defaults
```

**문제**:
- 동일한 `query_type`에 대해 매번 Neo4j 쿼리 실행
- 불필요한 네트워크 I/O
- 응답 시간 증가

---

## ✅ 채택: 전역 캐시 방식 (Option 2)

**결정**: 전역 캐시 방식만 구현합니다.

**이유**:
- 단일 KG 인스턴스만 사용 (현재 프로젝트)
- 메모리 효율적 (프로세스당 ~128KB)
- 캐시 무효화 용이 (단일 진입점)
- 캐시 통계 명확 (전체 히트율)

**⚠️ 인스턴스별 캐시는 구현하지 않습니다.**

---

## 구현 방법

### src/qa/rule_loader.py (전체 교체)

```python
"""규칙 로더 - 전역 캐싱."""
from __future__ import annotations
from functools import lru_cache
from typing import TYPE_CHECKING, Optional, List
import logging

if TYPE_CHECKING:
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


# ===== 전역 상태 =====
_GLOBAL_KG: Optional[QAKnowledgeGraph] = None


def set_global_kg(kg: Optional[QAKnowledgeGraph]) -> None:
    """
    전역 KG 설정.
    
    ⚠️ 호출 위치: src/web/api.py의 init_resources()에서 호출
    
    Args:
        kg: QAKnowledgeGraph 인스턴스 (None이면 캐싱 비활성화)
    """
    global _GLOBAL_KG
    _GLOBAL_KG = kg
    logger.info("Global KG set for RuleLoader cache: %s", kg is not None)


# ===== 전역 캐시 함수 =====
@lru_cache(maxsize=128)
def _load_rules_from_global_kg(query_type: str) -> tuple[str, ...]:
    """
    전역 KG를 사용한 규칙 로드 (전역 캐싱).
    
    ⚠️ 주의:
    - 반드시 set_global_kg()를 먼저 호출해야 합니다
    - 모든 RuleLoader 인스턴스가 이 캐시를 공유합니다
    - 프로세스당 하나의 캐시 (멀티프로세스 시 독립)
    
    Args:
        query_type: 질의 타입 (예: "explanation", "target_short")
    
    Returns:
        규칙 텍스트 튜플 (불변 타입)
    """
    if _GLOBAL_KG is None:
        logger.debug("Global KG not set, returning empty rules")
        return tuple()
    
    try:
        kg_rules = _GLOBAL_KG.get_rules_for_query_type(query_type)
        rules = [r.get("text") for r in kg_rules if r.get("text")]
        logger.debug(
            "Loaded %d rules for type=%s from Neo4j (global cache)",
            len(rules),
            query_type
        )
        return tuple(rules)  # 불변 타입으로 캐싱
    except Exception as e:
        logger.warning("Rule 로드 실패 (type=%s): %s", query_type, e)
        return tuple()


def clear_global_rule_cache() -> None:
    """
    전역 규칙 캐시 초기화.
    
    ⚠️ 호출 시점:
    1. Neo4j 규칙 업데이트 후 (수동 또는 자동)
    2. 캐시 문제 디버깅 시
    3. 성능 테스트 초기화 시
    """
    _load_rules_from_global_kg.cache_clear()
    logger.info("Global rule cache cleared")


def get_global_cache_info() -> dict:
    """
    전역 캐시 통계.
    
    Returns:
        hits, misses, maxsize, currsize, hit_rate
    """
    cache_info = _load_rules_from_global_kg.cache_info()
    return {
        "hits": cache_info.hits,
        "misses": cache_info.misses,
        "maxsize": cache_info.maxsize,
        "currsize": cache_info.currsize,
        "hit_rate": (
            cache_info.hits / (cache_info.hits + cache_info.misses)
            if (cache_info.hits + cache_info.misses) > 0
            else 0.0
        ),
    }


# ===== RuleLoader 클래스 =====
class RuleLoader:
    """
    Neo4j에서 규칙을 로드하는 클래스 (전역 캐시 사용).
    
    ⚠️ 캐시 범위:
    - 전역 캐시를 사용하므로 모든 RuleLoader 인스턴스가 캐시를 공유합니다
    - 프로세스당 하나의 캐시 (멀티프로세스 환경에서는 프로세스별 독립)
    """
    
    def __init__(self, kg: Optional[QAKnowledgeGraph]):
        """
        RuleLoader 초기화.
        
        Args:
            kg: QAKnowledgeGraph 인스턴스 (호환성 유지용, 실제로는 사용 안 함)
        
        Note:
            실제 쿼리는 set_global_kg()로 설정된 전역 KG를 사용합니다.
            kg 파라미터는 기존 코드 호환성을 위해 유지됩니다.
        """
        self.kg = kg  # 호환성 유지 (사용 안 함)
    
    def get_rules_for_type(
        self, query_type: str, defaults: List[str]
    ) -> List[str]:
        """
        규칙 로드 (전역 캐싱 사용).
        
        Args:
            query_type: 질의 타입
            defaults: KG 없거나 실패 시 기본값
        
        Returns:
            규칙 리스트
        """
        cached_rules = _load_rules_from_global_kg(query_type)
        
        if cached_rules:
            logger.debug("Global cache hit for type=%s", query_type)
            return list(cached_rules)
        
        # 캐시 미스 또는 KG 없음 → 기본값 반환
        return defaults
    
    def clear_cache(self) -> None:
        """
        전역 캐시 초기화 (래퍼 메서드).
        
        ⚠️ 주의: 이 메서드는 전역 캐시를 초기화하므로
        모든 RuleLoader 인스턴스에 영향을 줍니다.
        """
        clear_global_rule_cache()
    
    def get_cache_info(self) -> dict:
        """전역 캐시 통계 (래퍼 메서드)."""
        return get_global_cache_info()
```

---

## 애플리케이션 초기화

### src/web/api.py 수정

```python
async def init_resources() -> None:
    """리소스 초기화 - ServiceRegistry 사용."""
    registry = get_registry()
    
    if registry.is_initialized():
        logger.info("Resources already initialized")
        return
    
    # ... 기존 초기화 (config, agent) ...
    
    # ===== KG 초기화 및 전역 설정 =====
    from src.qa.rule_loader import set_global_kg
    
    try:
        knowledge_graph = QAKnowledgeGraph()
        registry.register_kg(knowledge_graph)
        
        # 전역 KG 설정 (RuleLoader 캐싱 활성화)
        set_global_kg(knowledge_graph)
        
        logger.info("QAKnowledgeGraph initialized (global cache enabled)")
    except Exception as e:
        logger.warning("Neo4j connection failed (RAG disabled): %s", e)
        registry.register_kg(None)
        
        # KG 없으면 전역 KG도 None 설정
        set_global_kg(None)
    
    # ... 기존 초기화 (pipeline, routers) ...
```

---

## 캐시 무효화 전략

### 운영 플로우

```text
┌─────────────────────────────────────────────────────────┐
│ 규칙 변경 시나리오                                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ 1. QAKnowledgeGraph API 사용 (자동 무효화) ✅             │
│    ├─ kg.update_rule()  → 자동 캐시 초기화              │
│    ├─ kg.add_rule()     → 자동 캐시 초기화              │
│    └─ kg.delete_rule()  → 자동 캐시 초기화              │
│                                                           │
│ 2. Neo4j 직접 수정 (수동 무효화 필요) ⚠️                 │
│    ├─ Cypher 쿼리로 규칙 수정                            │
│    ├─ 수동: clear_global_rule_cache() 호출              │
│    └─ 또는: 서버 재시작 (프로세스 종료 시 자동 초기화)    │
│                                                           │
│ 3. 애플리케이션 재시작 (자동 초기화) ✅                   │
│    └─ 프로세스 종료 → 캐시 메모리 해제                   │
│                                                           │
└─────────────────────────────────────────────────────────┘

⚠️ 중요: Neo4j를 직접 수정하면 반드시 캐시 무효화를 해야 합니다!
```

### 자동 무효화 구현 (선택)

#### src/qa/rag_system.py 수정

```python
class QAKnowledgeGraph:
    """
    Q&A 지식 그래프.
    
    규칙 변경 메서드는 자동으로 RuleLoader 캐시를 무효화합니다.
    """
    
    def update_rule(self, rule_id: str, new_text: str) -> None:
        """
        규칙 업데이트 및 자동 캐시 무효화.
        
        운영 플로우:
        1. Neo4j에 규칙 업데이트
        2. 자동으로 RuleLoader 전역 캐시 초기화
        3. 다음 요청부터 새 규칙 반영
        """
        # 1. Neo4j 업데이트
        with self.driver.session() as session:
            session.run(
                "MATCH (r:Rule {id: $rule_id}) SET r.text = $new_text",
                rule_id=rule_id,
                new_text=new_text
            )
        logger.info("Rule updated in Neo4j: id=%s", rule_id)
        
        # 2. 캐시 무효화
        from src.qa.rule_loader import clear_global_rule_cache
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after update")
    
    def add_rule(self, query_type: str, rule_text: str) -> str:
        """규칙 추가 및 자동 캐시 무효화."""
        # Neo4j에 추가
        rule_id = self._add_rule_to_neo4j(query_type, rule_text)
        logger.info("Rule added to Neo4j: id=%s", rule_id)
        
        # 캐시 무효화
        from src.qa.rule_loader import clear_global_rule_cache
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after add")
        
        return rule_id
    
    def delete_rule(self, rule_id: str) -> None:
        """규칙 삭제 및 자동 캐시 무효화."""
        # Neo4j에서 삭제
        self._delete_rule_from_neo4j(rule_id)
        logger.info("Rule deleted from Neo4j: id=%s", rule_id)
        
        # 캐시 무효화
        from src.qa.rule_loader import clear_global_rule_cache
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after delete")
```

---

## 관리자 엔드포인트 (선택)

### ⚠️ 보안 주의

```text
┌─────────────────────────────────────────────────────────┐
│ 관리자 엔드포인트 사용 제한                                │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ ✅ 허용: 로컬 개발 환경 (localhost:8000)                  │
│ ✅ 허용: 개인 테스트 서버 (방화벽 내부)                    │
│                                                           │
│ ❌ 금지: 외부 접근 가능한 프로덕션 서버                    │
│ ❌ 금지: 공개 인터넷 노출                                 │
│                                                           │
│ 프로덕션 배포 시:                                         │
│ - [ ] 엔드포인트 완전 비활성화 (router 등록 제거)         │
│ - [ ] 또는 JWT/API Key 인증 추가                         │
│ - [ ] 또는 Nginx IP 화이트리스트 설정                    │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### src/web/routers/admin.py (신규)

```python
"""
관리자용 엔드포인트.

⚠️⚠️⚠️ 중요 보안 경고 ⚠️⚠️⚠️

이 엔드포인트는 인증이 없습니다!

✅ 사용 가능: 로컬 개발 환경 (localhost)
✅ 사용 가능: 개인 테스트 서버 (내부 네트워크)

❌ 절대 금지: 외부 접근 가능한 프로덕션 서버
❌ 절대 금지: 공개 인터넷 노출

프로덕션 배포 시 반드시 다음 중 하나를 적용:
1. 이 router 등록 제거 (권장)
2. JWT 토큰 인증 추가
3. Nginx에서 IP 화이트리스트 설정
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    캐시 통계 조회.
    
    ⚠️ 로컬/테스트 전용 - 인증 없음
    
    Returns:
        {
            "cache": {
                "hits": 100,
                "misses": 5,
                "hit_rate": 0.95,
                "currsize": 8,
                "maxsize": 128
            },
            "status": "ok"
        }
    """
    from src.qa.rule_loader import get_global_cache_info
    
    try:
        cache_info = get_global_cache_info()
        logger.info("Cache stats requested: hit_rate=%.2f", cache_info["hit_rate"])
        return {
            "cache": cache_info,
            "status": "ok",
        }
    except Exception as e:
        logger.error("Failed to get cache stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """
    전역 캐시 초기화.
    
    ⚠️ 로컬/테스트 전용 - 인증 없음
    ⚠️ 모든 RuleLoader 캐시가 초기화됨
    
    사용 시나리오:
    - Neo4j 규칙을 Cypher로 직접 수정한 후
    - 캐시 문제 디버깅
    - 성능 테스트 초기화
    
    Returns:
        {"message": "...", "status": "ok"}
    """
    from src.qa.rule_loader import clear_global_rule_cache
    
    try:
        clear_global_rule_cache()
        logger.warning("Global rule cache cleared via admin API")
        return {
            "message": "Global rule cache cleared",
            "status": "ok",
        }
    except Exception as e:
        logger.error("Failed to clear cache: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/health")
async def cache_health() -> Dict[str, Any]:
    """
    캐시 헬스체크.
    
    캐시 히트율이 50% 미만이면 경고.
    
    Returns:
        {
            "status": "ok" | "warning",
            "hit_rate": 0.95,
            "message": "...",
            "cache": {...}
        }
    """
    from src.qa.rule_loader import get_global_cache_info
    
    cache_info = get_global_cache_info()
    hit_rate = cache_info["hit_rate"]
    
    # 히트율 50% 미만이면 경고
    status = "ok" if hit_rate >= 0.5 else "warning"
    message = (
        "Cache healthy" 
        if status == "ok" 
        else "Low cache hit rate - check query patterns or increase maxsize"
    )
    
    logger.info("Cache health check: status=%s, hit_rate=%.2f", status, hit_rate)
    
    return {
        "status": status,
        "hit_rate": hit_rate,
        "message": message,
        "cache": cache_info,
    }
```

### src/web/api.py에 라우터 등록 (선택)

```python
# ⚠️ 로컬/테스트 환경에서만 활성화
# 프로덕션 배포 시 이 라인을 주석 처리하거나 제거하세요!

from src.web.routers import admin as admin_router

# 관리자 엔드포인트 등록 (로컬 전용)
if app.debug or os.getenv("ENABLE_ADMIN_API") == "true":
    app.include_router(admin_router.router)
    logger.warning("Admin API enabled - DO NOT USE IN PRODUCTION")
else:
    logger.info("Admin API disabled (production mode)")
```

---

## 테스트

### tests/unit/qa/test_rule_loader_cache.py (신규)

```python
"""RuleLoader 전역 캐싱 테스트."""
import pytest
from unittest.mock import Mock, MagicMock
from src.qa.rule_loader import (
    RuleLoader,
    set_global_kg,
    clear_global_rule_cache,
    get_global_cache_info,
)


@pytest.fixture(autouse=True)
def reset_global_cache():
    """각 테스트 전후 전역 캐시 초기화."""
    clear_global_rule_cache()
    set_global_kg(None)
    yield
    clear_global_rule_cache()
    set_global_kg(None)


def test_global_cache_hit():
    """전역 캐시 히트 테스트."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        return_value=[
            {"text": "규칙 1"},
            {"text": "규칙 2"},
        ]
    )
    set_global_kg(mock_kg)
    
    loader = RuleLoader(mock_kg)
    
    # 첫 번째 호출 (캐시 미스)
    rules1 = loader.get_rules_for_type("explanation", [])
    assert len(rules1) == 2
    assert mock_kg.get_rules_for_query_type.call_count == 1
    
    # 두 번째 호출 (캐시 히트)
    rules2 = loader.get_rules_for_type("explanation", [])
    assert len(rules2) == 2
    assert mock_kg.get_rules_for_query_type.call_count == 1  # 증가 안 함!


def test_global_cache_shared_across_instances():
    """서로 다른 RuleLoader 인스턴스가 캐시를 공유."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        return_value=[{"text": "공유 규칙"}]
    )
    set_global_kg(mock_kg)
    
    # 첫 번째 인스턴스
    loader1 = RuleLoader(mock_kg)
    rules1 = loader1.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1
    
    # 두 번째 인스턴스 (캐시 히트!)
    loader2 = RuleLoader(mock_kg)
    rules2 = loader2.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1  # 증가 안 함!
    assert rules1 == rules2


def test_cache_info():
    """캐시 통계 확인."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        return_value=[{"text": "규칙 1"}]
    )
    set_global_kg(mock_kg)
    
    loader = RuleLoader(mock_kg)
    
    # 초기 상태
    info = get_global_cache_info()
    assert info["hits"] == 0
    assert info["misses"] == 0
    
    # 첫 호출 (미스)
    loader.get_rules_for_type("explanation", [])
    info = get_global_cache_info()
    assert info["misses"] == 1
    assert info["hits"] == 0
    
    # 재호출 (히트)
    loader.get_rules_for_type("explanation", [])
    info = get_global_cache_info()
    assert info["hits"] == 1
    assert info["misses"] == 1
    assert info["hit_rate"] == 0.5  # 50%


def test_clear_global_cache():
    """전역 캐시 초기화."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        return_value=[{"text": "규칙 1"}]
    )
    set_global_kg(mock_kg)
    
    loader = RuleLoader(mock_kg)
    
    # 첫 호출
    loader.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1
    
    # 재호출 (캐시 히트)
    loader.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1
    
    # 캐시 초기화
    clear_global_rule_cache()
    
    # 재호출 (캐시 미스)
    loader.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 2  # 증가!


def test_no_global_kg_set():
    """KG 설정 안 했을 때 기본값 반환."""
    # set_global_kg() 호출 안 함
    loader = RuleLoader(None)
    
    defaults = ["기본 규칙 1", "기본 규칙 2"]
    rules = loader.get_rules_for_type("explanation", defaults)
    
    assert rules == defaults


def test_kg_exception():
    """KG 예외 발생 시 기본값 반환."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        side_effect=Exception("Neo4j error")
    )
    set_global_kg(mock_kg)
    
    loader = RuleLoader(mock_kg)
    
    defaults = ["기본 규칙 1"]
    rules = loader.get_rules_for_type("explanation", defaults)
    
    assert rules == defaults
```

---

## 적용 순서

### ✅ 실행 지침: Option 2 (전역 캐시)만 채택

인스턴스별 캐시는 구현하지 않습니다. 아래 순서대로 전역 캐시만 적용하세요.

### Day 1: 구현 (2-3시간)

```bash
# 1. src/qa/rule_loader.py 전체 교체
#    - 위의 "src/qa/rule_loader.py (전체 교체)" 코드로 교체
#    - NotImplementedError 없는 깔끔한 버전

# 2. src/web/api.py 수정
#    - init_resources()에 set_global_kg() 추가

# 3. src/qa/rag_system.py 수정 (선택)
#    - update_rule() 등에 자동 캐시 무효화 추가

# 4. tests/unit/qa/test_rule_loader_cache.py 생성

# 5. 테스트 실행
pytest tests/unit/qa/test_rule_loader_cache.py -v
```

### Day 2: 검증 및 모니터링 (1-2시간)

```bash
# 1. 관리자 엔드포인트 추가 (선택)
#    - src/web/routers/admin.py 생성
#    - src/web/api.py에 조건부 라우터 등록

# 2. 전체 테스트
pytest tests/ -v

# 3. 로컬 서버 테스트
uvicorn src.web.api:app --reload

# 4. 캐시 통계 확인 (관리자 API 활성화한 경우)
curl http://localhost:8000/api/admin/cache/stats

# 5. 수동 캐시 초기화 테스트
curl -X POST http://localhost:8000/api/admin/cache/clear
```

---

## 선택사항 TODO

### ✅ 필수 (Phase 7 완료 기준)
- [ ] `src/qa/rule_loader.py` 전체 교체 (전역 캐시 버전)
- [ ] `src/web/api.py`에 `set_global_kg()` 호출 추가
- [ ] `test_rule_loader_cache.py` 작성 및 통과
- [ ] 전체 테스트 통과 확인 (`pytest tests/ -v`)

### 🔧 선택 (운영 편의)
- [ ] 자동 캐시 무효화
  - [ ] `QAKnowledgeGraph.update_rule()` 수정
  - [ ] `QAKnowledgeGraph.add_rule()` 수정
  - [ ] `QAKnowledgeGraph.delete_rule()` 수정
- [ ] 관리자 엔드포인트 (로컬 전용)
  - [ ] `src/web/routers/admin.py` 생성
  - [ ] `src/web/api.py`에 조건부 등록
  - [ ] `/api/admin/cache/stats` 테스트
  - [ ] `/api/admin/cache/clear` 테스트
  - [ ] `/api/admin/cache/health` 테스트

### 🚀 프로덕션 준비 (배포 전)
- [ ] 관리자 API 비활성화 또는 인증 추가
- [ ] 캐시 메트릭 모니터링 설정 (선택)
- [ ] 운영 가이드 문서화

---

## 예상 성능 향상

### Before (캐싱 없음)

```text
워크플로우 100회 실행:
├─ Neo4j 쿼리: 100회 × 50ms = 5,000ms
└─ 총 시간: 5초
```

### After (전역 캐싱)

```text
워크플로우 100회 실행:
├─ 첫 호출: 1회 × 50ms = 50ms (캐시 미스)
├─ 나머지 99회: 99회 × 0.01ms = 1ms (캐시 히트)
└─ 총 시간: 51ms (99% 감소!)

캐시 히트율: 99%
```

---

## 주의사항

### 1. 메모리 사용량
```text
프로세스당: ~128KB (maxsize=128)
Gunicorn 워커 4개: 4 × 128KB = 512KB (무시 가능)
```

### 2. 멀티프로세스 환경
```text
Gunicorn 멀티워커:
├─ 각 워커가 독립적인 전역 캐시 보유
├─ 워커 간 캐시 공유 불가
└─ 워커 4개 = 전역 캐시 4개

프로세스 간 캐시 공유 필요 시:
└─ Redis 기반 분산 캐시 고려 (Phase 8)
```

### 3. 캐시 무효화 타이밍
```text
자동:
- 애플리케이션 재시작 (프로세스 종료)
- QAKnowledgeGraph API 사용 (자동 무효화 구현 시)

수동:
- Neo4j 직접 수정 후 clear_global_rule_cache() 호출
- 또는 서버 재시작
```

---

## 롤백 방법

```bash
# 전역 캐시 구현 제거
git checkout HEAD -- src/qa/rule_loader.py
git checkout HEAD -- src/web/api.py
git checkout HEAD -- tests/unit/qa/test_rule_loader_cache.py

# 관리자 API도 제거 (추가했다면)
git checkout HEAD -- src/web/routers/admin.py

# 테스트 확인
pytest tests/ -v
```

---

## 결론

### Phase 7 최종 결정

**✅ 채택: 전역 캐시 방식 (Option 2)만 구현**

**특징**:
- 모든 RuleLoader 인스턴스가 하나의 전역 캐시 공유
- 프로세스당 ~128KB 메모리 (무시 가능)
- 캐시 통계 명확 (전체 히트율)
- 무효화 용이 (단일 진입점)

### 예상 효과

| 항목 | 수치 |
|------|------|
| **Neo4j 쿼리 감소** | 99% |
| **평균 응답 시간 단축** | 20-30% |
| **캐시 히트율** | 95%+ 예상 |
| **메모리 증가** | ~128KB (무시 가능) |
| **구현 시간** | 2-3시간 |
| **위험도** | 매우 낮음 |

### 적용 권장 시점

**Phase 1-6이 안정화된 후 적용하세요!**

### 최종 체크리스트

#### ✅ 필수
- [ ] src/qa/rule_loader.py 전체 교체 (전역 캐시)
- [ ] src/web/api.py에 set_global_kg() 추가
- [ ] 테스트 작성 및 모두 통과
- [ ] 운영 플로우 이해 (캐시 무효화 시점)

#### 🔧 선택
- [ ] 자동 캐시 무효화 (QAKnowledgeGraph API)
- [ ] 관리자 엔드포인트 (로컬 전용)

#### 🚀 프로덕션 배포 시
- [ ] 관리자 API 비활성화 또는 인증 추가
- [ ] 운영 가이드 문서화
```