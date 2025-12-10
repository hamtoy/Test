"""Legacy-compatible dependency helpers and service container."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, HTTPException
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
        """Reset all cached services."""
        cls._config = None
        cls._agent = None
        cls._kg = None
        cls._mm = None
        cls._pipeline = None

    @classmethod
    def set_config(cls, config: AppConfig) -> None:
        """Set the global config instance."""
        cls._config = config

    @classmethod
    def set_agent(cls, agent: GeminiAgent) -> None:
        """Set the global agent instance."""
        cls._agent = agent

    @classmethod
    def set_kg(cls, kg: QAKnowledgeGraph | None) -> None:
        """Set the global knowledge graph instance."""
        cls._kg = kg

    @classmethod
    def set_pipeline(cls, pipeline: IntegratedQAPipeline | None) -> None:
        """Set the global pipeline instance."""
        cls._pipeline = pipeline

    @classmethod
    def get_config(cls) -> AppConfig:
        """Get or create the global config."""
        if cls._config is None:
            cls._config = get_app_config()
        return cls._config

    @classmethod
    def get_agent(cls, config: AppConfig | None = None) -> GeminiAgent | None:
        """Get or create the global agent."""
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
        """Get or create the global knowledge graph."""
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
        """Get or create the global pipeline."""
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
        """Get or create the multimodal handler."""
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
    """Get the global config."""
    return ServiceContainer.get_config()


def get_agent(config: AppConfig | None = None) -> GeminiAgent | None:
    """Get the global agent."""
    return ServiceContainer.get_agent(config)


def get_knowledge_graph() -> QAKnowledgeGraph | None:
    """Get the global knowledge graph."""
    return ServiceContainer.get_knowledge_graph()


def get_multimodal() -> object | None:
    """Get the global multimodal handler."""
    return ServiceContainer.get_multimodal()


def get_pipeline() -> IntegratedQAPipeline | None:
    """Get the global pipeline."""
    return ServiceContainer.get_pipeline()


# Legacy alias for previous code paths/tests
container: type[ServiceContainer] = ServiceContainer


# ============================================================================
# FastAPI Depends Pattern - Async Dependencies with Type Aliases
# ============================================================================
# Usage in routers:
#   from src.web.dependencies import AgentDep, ConfigDep
#   @router.post("/endpoint")
#   async def endpoint(agent: AgentDep, config: ConfigDep): ...
# ============================================================================


async def require_agent() -> GeminiAgent:
    """Require an initialized agent.

    Raises:
        HTTPException: 500 if agent is not initialized.
    """
    agent = ServiceContainer.get_agent()
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")
    return agent


async def require_config() -> AppConfig:
    """Return the app config."""
    return ServiceContainer.get_config()


async def require_knowledge_graph() -> QAKnowledgeGraph:
    """Require knowledge graph.

    Raises:
        HTTPException: 500 if KG is not initialized.
    """
    kg = ServiceContainer.get_knowledge_graph()
    if kg is None:
        raise HTTPException(status_code=500, detail="Knowledge Graph 초기화 실패")
    return kg


async def require_pipeline() -> IntegratedQAPipeline:
    """Require pipeline.

    Raises:
        HTTPException: 500 if pipeline is not initialized.
    """
    pipeline = ServiceContainer.get_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline 초기화 실패")
    return pipeline


# Type aliases for cleaner endpoint signatures
AgentDep = Annotated[GeminiAgent, Depends(require_agent)]
ConfigDep = Annotated[AppConfig, Depends(require_config)]
KnowledgeGraphDep = Annotated[QAKnowledgeGraph, Depends(require_knowledge_graph)]
PipelineDep = Annotated[IntegratedQAPipeline, Depends(require_pipeline)]


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
    # FastAPI Depends aliases
    "AgentDep",
    "ConfigDep",
    "KnowledgeGraphDep",
    "PipelineDep",
    "require_agent",
    "require_config",
    "require_knowledge_graph",
    "require_pipeline",
]
