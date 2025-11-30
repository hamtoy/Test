"""FastAPI dependency injection for web API services.

Provides factory functions for injecting services into API endpoints,
enabling better testability and horizontal scaling.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from fastapi import Depends

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.features.multimodal import MultimodalUnderstanding
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# Repository root for template loading
REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache()
def get_app_config() -> "AppConfig":
    """Get cached application configuration.

    Returns:
        AppConfig instance (singleton)
    """
    from src.config import AppConfig

    return AppConfig()


def get_jinja_env() -> Any:
    """Get Jinja2 environment for template rendering.

    Returns:
        Configured Jinja2 Environment
    """
    from jinja2 import Environment, FileSystemLoader

    return Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


class ServiceContainer:
    """Container for lazily initialized services.

    Provides singleton instances of services that are expensive
    to create, such as AI agents and database connections.
    """

    _agent: Optional["GeminiAgent"] = None
    _kg: Optional["QAKnowledgeGraph"] = None
    _mm: Optional["MultimodalUnderstanding"] = None

    @classmethod
    def get_agent(
        cls, config: "AppConfig" = Depends(get_app_config)
    ) -> Optional["GeminiAgent"]:
        """Get or create GeminiAgent instance.

        Args:
            config: Application configuration

        Returns:
            GeminiAgent instance or None if initialization fails
        """
        if cls._agent is None:
            from src.agent import GeminiAgent

            cls._agent = GeminiAgent(
                config=config,
                jinja_env=get_jinja_env(),
            )
            logger.info("GeminiAgent initialized via DI")
        return cls._agent

    @classmethod
    def get_knowledge_graph(cls) -> Optional["QAKnowledgeGraph"]:
        """Get or create QAKnowledgeGraph instance.

        Returns:
            QAKnowledgeGraph instance or None if Neo4j unavailable
        """
        if cls._kg is None:
            try:
                from src.qa.rag_system import QAKnowledgeGraph

                cls._kg = QAKnowledgeGraph()
                logger.info("QAKnowledgeGraph initialized via DI")
            except Exception as e:
                logger.warning("Neo4j connection failed: %s", e)
        return cls._kg

    @classmethod
    def get_multimodal(cls) -> Optional["MultimodalUnderstanding"]:
        """Get or create MultimodalUnderstanding instance.

        Returns:
            MultimodalUnderstanding instance or None if prerequisites missing
        """
        if cls._mm is None:
            kg = cls.get_knowledge_graph()
            if kg is not None:
                from src.features.multimodal import MultimodalUnderstanding

                cls._mm = MultimodalUnderstanding(kg=kg)
                logger.info("MultimodalUnderstanding initialized via DI")
        return cls._mm

    @classmethod
    def reset(cls) -> None:
        """Reset all service instances (for testing)."""
        cls._agent = None
        cls._kg = None
        cls._mm = None


# Dependency functions for FastAPI
def get_agent(
    config: "AppConfig" = Depends(get_app_config),
) -> Optional["GeminiAgent"]:
    """FastAPI dependency for GeminiAgent.

    Args:
        config: Injected application configuration

    Returns:
        GeminiAgent instance
    """
    return ServiceContainer.get_agent(config)


def get_knowledge_graph() -> Optional["QAKnowledgeGraph"]:
    """FastAPI dependency for QAKnowledgeGraph.

    Returns:
        QAKnowledgeGraph instance or None
    """
    return ServiceContainer.get_knowledge_graph()


def get_multimodal() -> Optional["MultimodalUnderstanding"]:
    """FastAPI dependency for MultimodalUnderstanding.

    Returns:
        MultimodalUnderstanding instance or None
    """
    return ServiceContainer.get_multimodal()


__all__ = [
    "get_app_config",
    "get_agent",
    "get_knowledge_graph",
    "get_multimodal",
    "ServiceContainer",
    "REPO_ROOT",
]
