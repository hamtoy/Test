"""Lightweight service container for web layer dependencies."""

from __future__ import annotations

from typing import Optional

from src.agent import GeminiAgent
from src.config import AppConfig
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph


class ServiceContainer:
    """Simple dependency container to avoid scattered globals."""

    def __init__(self) -> None:
        self._config: Optional[AppConfig] = None
        self._agent: Optional[GeminiAgent] = None
        self._kg: Optional[QAKnowledgeGraph] = None
        self._pipeline: Optional[IntegratedQAPipeline] = None

    def set_config(self, config: AppConfig) -> None:
        self._config = config

    def set_agent(self, agent: GeminiAgent) -> None:
        self._agent = agent

    def set_kg(self, kg: Optional[QAKnowledgeGraph]) -> None:
        self._kg = kg

    def set_pipeline(self, pipeline: Optional[IntegratedQAPipeline]) -> None:
        self._pipeline = pipeline

    def get_config(self) -> AppConfig:
        if self._config is None:
            raise RuntimeError("Config not initialized")
        return self._config

    def get_agent(self) -> GeminiAgent:
        if self._agent is None:
            raise RuntimeError("Agent not initialized")
        return self._agent

    def get_kg(self) -> Optional[QAKnowledgeGraph]:
        return self._kg

    def get_pipeline(self) -> Optional[IntegratedQAPipeline]:
        return self._pipeline


# Global container instance (still module-level, but centralized)
container = ServiceContainer()


def get_config() -> AppConfig:
    return container.get_config()


def get_agent() -> GeminiAgent:
    return container.get_agent()


def get_kg() -> Optional[QAKnowledgeGraph]:
    return container.get_kg()


def get_pipeline() -> Optional[IntegratedQAPipeline]:
    return container.get_pipeline()
