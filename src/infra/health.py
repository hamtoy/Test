# mypy: disable-error-code=attr-defined
from __future__ import annotations

import asyncio
import datetime
import inspect
import logging
import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

try:
    import psutil
except (
    ImportError
):  # pragma: no cover - provide stub so tests can patch psutil.virtual_memory
    import types

    psutil = types.ModuleType("psutil")

    def _virtual_memory_stub() -> Any:
        raise ImportError("psutil not installed")

    psutil.virtual_memory = _virtual_memory_stub
    sys.modules["psutil"] = psutil

if TYPE_CHECKING:
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# 타임아웃 설정 (초)
DEFAULT_TIMEOUT = 3.0


async def check_redis() -> dict[str, Any]:
    """Redis 연결 및 응답 시간 확인 (타임아웃 3초).

    Returns:
        Redis 상태 정보 딕셔너리

    """
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return {"status": "skipped", "reason": "REDIS_URL not configured"}

    try:
        import redis.asyncio as aioredis

        async def _check_redis() -> dict[str, Any]:
            start = time.perf_counter()
            client = aioredis.from_url(redis_url)
            await client.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            await client.close()
            return {
                "status": "up",
                "latency_ms": round(latency_ms, 2),
                "message": "Redis is healthy",
            }

        return await asyncio.wait_for(_check_redis(), timeout=DEFAULT_TIMEOUT)
    except asyncio.TimeoutError:
        return {"status": "down", "error": f"Timeout (>{DEFAULT_TIMEOUT}s)"}
    except ImportError:
        return {"status": "skipped", "reason": "redis package not installed"}
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {"status": "down", "error": str(exc)}


async def check_neo4j() -> dict[str, Any]:
    """Neo4j 연결 및 쿼리 테스트 (타임아웃 3초).

    Returns:
        Neo4j 상태 정보 딕셔너리

    """
    neo4j_uri = os.getenv("NEO4J_URI")
    if not neo4j_uri:
        return {"status": "skipped", "reason": "NEO4J_URI not configured"}

    try:
        import importlib.util

        if importlib.util.find_spec("neo4j") is None:
            return {"status": "skipped", "reason": "neo4j package not installed"}

        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")

        start = time.perf_counter()

        # run_in_executor로 동기 Neo4j 호출을 비동기로 래핑
        loop = asyncio.get_event_loop()

        async def _check_neo4j() -> bool:
            return await loop.run_in_executor(
                None,
                lambda: _sync_check_neo4j(neo4j_uri, neo4j_user, neo4j_password),
            )

        result = await asyncio.wait_for(_check_neo4j(), timeout=DEFAULT_TIMEOUT)

        if result:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "status": "up",
                "latency_ms": round(latency_ms, 2),
                "message": "Neo4j is healthy",
            }
        return {"status": "down", "error": "Connection check failed"}
    except asyncio.TimeoutError:
        return {"status": "down", "error": f"Timeout (>{DEFAULT_TIMEOUT}s)"}
    except ImportError:
        return {"status": "skipped", "reason": "neo4j package not installed"}
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return {"status": "down", "error": str(exc)}


def _sync_check_neo4j(uri: str, user: str, password: str) -> bool:
    """동기적으로 Neo4j 연결 확인."""
    from neo4j import GraphDatabase

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1").single()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()


async def check_gemini_api() -> dict[str, Any]:
    """Gemini API 키 유효성 확인.

    Returns:
        Gemini API 상태 정보 딕셔너리

    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "down", "error": "GEMINI_API_KEY not configured"}

    # API 키 형식 검증
    if not api_key.startswith("AIza"):
        return {"status": "down", "error": "Invalid API key format"}

    if len(api_key) != 39:
        return {"status": "down", "error": f"Invalid API key length: {len(api_key)}"}

    return {"status": "up", "key_prefix": api_key[:8] + "..."}


def check_dependencies() -> dict[str, Any]:
    """필수 의존성 버전 확인.

    Returns:
        의존성 버전 정보 딕셔너리

    """
    deps: dict[str, str | None] = {
        "python": sys.version.split()[0],
    }

    # pydantic 버전
    try:
        import pydantic

        deps["pydantic"] = pydantic.__version__
    except ImportError:
        deps["pydantic"] = None

    # google-generativeai 버전
    try:
        import google.generativeai

        deps["google-generativeai"] = getattr(
            google.generativeai,
            "__version__",
            "unknown",
        )
    except ImportError:
        deps["google-generativeai"] = None

    # fastapi 버전
    try:
        import fastapi

        deps["fastapi"] = fastapi.__version__
    except ImportError:
        deps["fastapi"] = None

    return {
        "status": "up",
        "dependencies": deps,
    }


async def check_disk() -> dict[str, Any]:
    """디스크 공간 확인.

    Returns:
        디스크 상태 정보 딕셔너리

    """
    try:
        import shutil

        total, used, free = shutil.disk_usage("/")
        usage_percent = (used / total) * 100

        status = "up"
        if usage_percent >= 95:
            status = "critical"
        elif usage_percent >= 90:
            status = "warning"

        return {
            "status": status,
            "usage_percent": round(usage_percent, 1),
            "free_gb": round(free / (1024**3), 2),
        }
    except Exception as exc:
        logger.warning("Disk health check failed: %s", exc)
        return {"status": "unknown", "error": str(exc)}


async def check_memory() -> dict[str, Any]:
    """메모리 사용량 확인.

    Returns:
        메모리 상태 정보 딕셔너리

    """
    try:
        # psutil이 없는 경우 /proc/meminfo에서 읽기 시도
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_percent = memory.percent
        except ImportError:
            # Linux에서 /proc/meminfo 파싱 (동기 파일 I/O는 스레드로 offload)
            def _read_meminfo() -> list[str]:
                return Path("/proc/meminfo").read_text().splitlines()

            lines = await asyncio.to_thread(_read_meminfo)

            mem_info: dict[str, int] = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    mem_info[key] = int(parts[1])

            total = mem_info.get("MemTotal", 1)
            available = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
            usage_percent = ((total - available) / total) * 100

        status = "up"
        if usage_percent >= 95:
            status = "critical"
        elif usage_percent >= 90:
            status = "warning"

        return {
            "status": status,
            "usage_percent": round(usage_percent, 1),
        }
    except Exception as exc:
        logger.warning("Memory health check failed: %s", exc)
        return {"status": "unknown", "error": str(exc)}


async def health_check_async() -> dict[str, Any]:
    """전체 헬스체크 실행 (비동기).

    Returns:
        전체 상태 정보 딕셔너리

    """
    # Dependencies are checked synchronously
    try:
        deps_result = check_dependencies()
    except Exception as exc:  # noqa: BLE001
        deps_result = {"status": "error", "error": str(exc)}

    checks = await asyncio.gather(
        check_redis(),
        check_neo4j(),
        check_gemini_api(),
        check_disk(),
        check_memory(),
        return_exceptions=True,
    )

    # 예외 처리
    check_results: list[dict[str, Any]] = []
    for check in checks:
        if isinstance(check, BaseException):
            check_results.append({"status": "error", "error": str(check)})
        else:
            check_results.append(check)

    # Append dependencies check result
    check_results.append(deps_result)

    # 전체 상태 결정
    all_statuses = [c.get("status", "unknown") for c in check_results]
    if "down" in all_statuses or "critical" in all_statuses or "error" in all_statuses:
        overall_status = "unhealthy"
    elif "warning" in all_statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "checks": {
            "redis": check_results[0],
            "neo4j": check_results[1],
            "gemini": check_results[2],
            "disk": check_results[3],
            "memory": check_results[4],
            "dependencies": check_results[5],
        },
        "version": "3.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def check_neo4j_connection(kg: QAKnowledgeGraph | None = None) -> bool:
    """Return True if a simple Neo4j query succeeds."""
    try:
        from neo4j.exceptions import Neo4jError
    except ImportError:
        logging.getLogger(__name__).warning(
            "Cannot check Neo4j connection: neo4j package not available",
        )
        return False

    if kg is None:
        try:
            from src.qa.rag_system import QAKnowledgeGraph

            kg = QAKnowledgeGraph()
        except ImportError:
            logging.getLogger(__name__).warning(
                "Cannot check Neo4j connection: QAKnowledgeGraph not available",
            )
            return False
    graph_obj = getattr(kg, "_graph", None)
    if graph_obj is None:
        return False
    try:
        with graph_obj.session() as session:
            session.run("RETURN 1").single()
        return True
    except Neo4jError:
        return False
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Neo4j health check failed: %s", exc)
        return False


def health_check() -> dict[str, Any]:
    """Basic health check report (동기)."""
    neo4j_ok = check_neo4j_connection()
    return {
        "status": "healthy" if neo4j_ok else "unhealthy",
        "neo4j": neo4j_ok,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def liveness_check() -> dict[str, Any]:
    """Kubernetes liveness probe - 프로세스 살아있는지 확인.

    Returns:
        간단한 상태 딕셔너리

    """
    return {"status": "ok"}


# ==================== Structured health reporting ====================


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class SystemHealth:
    status: HealthStatus
    timestamp: str
    version: str
    components: dict[str, ComponentHealth]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "components": {
                name: {
                    "status": comp.status.value,
                    "latency_ms": comp.latency_ms,
                    "message": comp.message,
                    "details": comp.details,
                }
                for name, comp in self.components.items()
            },
        }


class HealthChecker:
    """시스템 헬스 체커."""

    def __init__(self, version: str = "unknown"):
        self.version = version
        self._checks: dict[str, Any] = {}

    def register_check(self, name: str, check_fn: Any) -> None:
        """헬스 체크 함수 등록."""
        self._checks[name] = check_fn

    async def check_all(self) -> SystemHealth:
        """모든 컴포넌트 헬스 체크."""
        components: dict[str, ComponentHealth] = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_fn in self._checks.items():
            try:
                start = asyncio.get_event_loop().time()
                result = check_fn()
                if inspect.isawaitable(result):
                    result = await result
                latency = (asyncio.get_event_loop().time() - start) * 1000

                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency, 2),
                    details=result if isinstance(result, dict) else {"result": result},
                )
            except Exception as exc:  # noqa: BLE001, PERF203
                logger.warning("Health check failed for %s: %s", name, exc)
                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(exc),
                )
                overall_status = HealthStatus.UNHEALTHY

        unhealthy_count = sum(
            1 for c in components.values() if c.status == HealthStatus.UNHEALTHY
        )
        if 0 < unhealthy_count < len(components):
            overall_status = HealthStatus.DEGRADED

        return SystemHealth(
            status=overall_status,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            version=self.version,
            components=components,
        )


async def check_neo4j_with_params(uri: str, user: str, password: str) -> dict[str, Any]:
    """Parameterized Neo4j check using existing helper."""
    os.environ["NEO4J_URI"] = uri
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password
    return await check_neo4j()


async def check_redis_with_url(url: str) -> dict[str, Any]:
    """Parameterized Redis check."""
    os.environ["REDIS_URL"] = url
    return await check_redis()


async def readiness_check() -> dict[str, Any]:
    """Kubernetes readiness probe - Redis와 Neo4j만 체크.

    Returns:
        준비 상태 딕셔너리

    """
    checks = await asyncio.gather(
        check_redis(),
        check_neo4j(),
        return_exceptions=True,
    )

    check_results: list[dict[str, Any]] = []
    for check in checks:
        if isinstance(check, BaseException):
            check_results.append({"status": "error", "error": str(check)})
        else:
            check_results.append(check)

    # skipped 상태는 ready로 간주
    all_statuses = [
        c.get("status", "unknown")
        for c in check_results
        if c.get("status") != "skipped"
    ]
    is_ready = all(s in ("up",) for s in all_statuses) if all_statuses else True

    return {
        "ready": is_ready,
        "checks": {
            "redis": check_results[0],
            "neo4j": check_results[1],
        },
    }


__all__ = [
    "DEFAULT_TIMEOUT",
    "check_dependencies",
    "check_disk",
    "check_gemini_api",
    "check_memory",
    "check_neo4j",
    "check_neo4j_connection",
    "check_redis",
    "health_check",
    "health_check_async",
    "liveness_check",
    "readiness_check",
]
