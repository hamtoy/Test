"""서비스 레지스트리 - 싱글톤 패턴."""
from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.qa.pipeline import IntegratedQAPipeline
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """스레드 안전 서비스 레지스트리."""

    def __init__(self) -> None:
        self._config: Optional[AppConfig] = None
        self._agent: Optional[GeminiAgent] = None
        self._kg: Optional[QAKnowledgeGraph] = None
        self._pipeline: Optional[IntegratedQAPipeline] = None
        self._lock = threading.Lock()
        self._worker_id = os.getpid()

    def _check_worker(self) -> None:
        """프로세스가 바뀌면 경고 (멀티프로세스 디버깅용)."""
        current_pid = os.getpid()
        if current_pid != self._worker_id:
            logger.warning(
                "ServiceRegistry accessed from different process: "
                "original=%d, current=%d",
                self._worker_id,
                current_pid,
            )

    def register_config(self, config: AppConfig) -> None:
        """Config 등록."""
        with self._lock:
            self._config = config
            logger.debug("Config registered")

    def register_agent(self, agent: GeminiAgent) -> None:
        """Agent 등록."""
        with self._lock:
            self._agent = agent
            logger.debug("Agent registered")

    def register_kg(self, kg: Optional[QAKnowledgeGraph]) -> None:
        """KG 등록."""
        with self._lock:
            self._kg = kg
            logger.debug("KG registered: %s", kg is not None)

    def register_pipeline(self, pipeline: Optional[IntegratedQAPipeline]) -> None:
        """Pipeline 등록."""
        with self._lock:
            self._pipeline = pipeline
            logger.debug("Pipeline registered: %s", pipeline is not None)

    @property
    def config(self) -> AppConfig:
        """Config 가져오기."""
        self._check_worker()
        if self._config is None:
            raise RuntimeError("Config not registered. Call init_resources first.")
        return self._config

    @property
    def agent(self) -> GeminiAgent:
        """Agent 가져오기."""
        self._check_worker()
        if self._agent is None:
            raise RuntimeError("Agent not registered. Call init_resources first.")
        return self._agent

    @property
    def kg(self) -> Optional[QAKnowledgeGraph]:
        """KG 가져오기."""
        self._check_worker()
        return self._kg

    @property
    def pipeline(self) -> Optional[IntegratedQAPipeline]:
        """Pipeline 가져오기."""
        self._check_worker()
        return self._pipeline

    def is_initialized(self) -> bool:
        """초기화 여부 확인."""
        return self._config is not None and self._agent is not None

    def clear(self) -> None:
        """테스트용 초기화 - 프로덕션에서는 사용 금지."""
        with self._lock:
            self._config = None
            self._agent = None
            self._kg = None
            self._pipeline = None
            logger.warning("ServiceRegistry cleared (test mode only)")


# 전역 싱글톤 인스턴스
_registry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """레지스트리 접근자."""
    return _registry


def reset_registry_for_test() -> None:
    """테스트 전용 - 레지스트리 초기화."""
    _registry.clear()
