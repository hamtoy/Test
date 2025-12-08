"""Legacy-compatible dependency helpers and service container."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

from src.config import AppConfig

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.qa.pipeline import IntegratedQAPipeline
    from src.qa.rag_system import QAKnowledgeGraph
else:  # pragma: no cover - runtime import is lazy
    GeminiAgent = Any
    IntegratedQAPipeline = Any
    QAKnowledgeGraph = Any

# Backward-compatible constant
REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """Cached AppConfig."""
    return AppConfig()


@lru_cache(maxsize=1)
def get_jinja_env() -> Environment:
    """Cached Jinja2 environment."""
    return Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


class ServiceContainer:
    """Simple class-level container (legacy API compatible)."""

    _config: AppConfig | None = None
    _agent: GeminiAgent | None = None
    _kg: QAKnowledgeGraph | None = None
    _mm: object | None = None
    _pipeline: IntegratedQAPipeline | None = None

    @classmethod
    def reset(cls) -> None:
        cls._config = None
        cls._agent = None
        cls._kg = None
        cls._mm = None
        cls._pipeline = None

    @classmethod
    def set_config(cls, config: AppConfig) -> None:
        cls._config = config

    @classmethod
    def set_agent(cls, agent: GeminiAgent) -> None:
        cls._agent = agent

    @classmethod
    def set_kg(cls, kg: QAKnowledgeGraph | None) -> None:
        cls._kg = kg

    @classmethod
    def set_pipeline(cls, pipeline: IntegratedQAPipeline | None) -> None:
        cls._pipeline = pipeline

    @classmethod
    def get_config(cls) -> AppConfig:
        if cls._config is None:
            cls._config = get_app_config()
        return cls._config

    @classmethod
    def get_agent(cls, config: AppConfig | None = None) -> GeminiAgent | None:
        if cls._agent is not None:
            return cls._agent
        cfg = config or cls.get_config()
        try:
            from src.agent import GeminiAgent as Agent

            jinja_env = get_jinja_env()
            cls._agent = Agent(config=cfg, jinja_env=jinja_env)
        except Exception:
            cls._agent = None
        return cls._agent

    @classmethod
    def get_knowledge_graph(cls) -> QAKnowledgeGraph | None:
        if cls._kg is not None:
            return cls._kg
        try:
            from src.qa.rag_system import QAKnowledgeGraph as KG

            cls._kg = KG()
        except Exception:
            cls._kg = None
        return cls._kg

    @classmethod
    def get_pipeline(cls) -> IntegratedQAPipeline | None:
        if cls._pipeline is not None:
            return cls._pipeline
        try:
            from src.qa.pipeline import IntegratedQAPipeline as Pipeline

            cls._pipeline = Pipeline()
        except Exception:
            cls._pipeline = None
        return cls._pipeline

    @classmethod
    def get_multimodal(cls) -> object | None:
        if cls._mm is not None:
            return cls._mm
        kg = cls.get_knowledge_graph()
        if kg is None:
            return None
        try:
            from src.features.multimodal import MultimodalUnderstanding

            cls._mm = MultimodalUnderstanding(kg)
        except Exception:
            cls._mm = None
        return cls._mm


# Dependency wrappers (FastAPI-style)
def get_config() -> AppConfig:
    return ServiceContainer.get_config()


def get_agent(config: AppConfig | None = None) -> GeminiAgent | None:
    return ServiceContainer.get_agent(config)


def get_knowledge_graph() -> QAKnowledgeGraph | None:
    return ServiceContainer.get_knowledge_graph()


def get_multimodal() -> object | None:
    return ServiceContainer.get_multimodal()


def get_pipeline() -> IntegratedQAPipeline | None:
    return ServiceContainer.get_pipeline()


# Legacy alias for previous code paths/tests
container: type[ServiceContainer] = ServiceContainer

__all__ = [
    "REPO_ROOT",
    "ServiceContainer",
    "container",
    "get_agent",
    "get_app_config",
    "get_config",
    "get_jinja_env",
    "get_knowledge_graph",
    "get_multimodal",
    "get_pipeline",
]
