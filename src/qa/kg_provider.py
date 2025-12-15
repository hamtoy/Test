"""QAKnowledgeGraph singleton provider.

Provides a shared KG instance across all services to avoid
repeated connection pool initialization.

Usage:
    from src.qa.kg_provider import get_or_create_kg
    kg = get_or_create_kg()
"""

from __future__ import annotations

import logging
import threading
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

_kg_lock = threading.Lock()
_kg_instance: QAKnowledgeGraph | None = None


def get_or_create_kg() -> QAKnowledgeGraph:
    """Get or create a shared QAKnowledgeGraph instance.

    Thread-safe singleton pattern that:
    1. First checks ServiceRegistry (for web context)
    2. Falls back to module-level singleton
    3. Creates new instance only on first call

    Returns:
        Shared QAKnowledgeGraph instance
    """
    global _kg_instance

    # Fast path - already initialized
    instance = _kg_instance
    if instance is not None:
        return instance

    with _kg_lock:
        # Double-check after acquiring lock (another thread may have initialized)
        instance = _kg_instance
        if instance is not None:
            return instance

        # Check ServiceRegistry first (web context)
        try:
            from src.web.service_registry import get_registry

            registry_kg = get_registry().kg
            if registry_kg is not None:
                _kg_instance = registry_kg
                logger.debug("Using KG from ServiceRegistry")
                return registry_kg
        except (ImportError, RuntimeError):
            pass  # Registry not available or not initialized

        # Create new instance
        from src.qa.rag_system import QAKnowledgeGraph

        logger.debug("Creating new singleton QAKnowledgeGraph instance")
        new_instance = QAKnowledgeGraph()
        _kg_instance = new_instance
        return new_instance


def get_kg_if_available() -> QAKnowledgeGraph | None:
    """Get existing KG instance without creating a new one.

    Useful for optional operations that shouldn't trigger KG initialization.

    Returns:
        Existing KG instance or None if not initialized
    """
    global _kg_instance

    if _kg_instance is not None:
        return _kg_instance

    # Also check registry
    try:
        from src.web.service_registry import get_registry

        return get_registry().kg
    except (ImportError, RuntimeError):
        return None


def reset_kg_for_test() -> None:
    """Reset the singleton for testing. NOT for production use."""
    global _kg_instance
    with _kg_lock:
        if _kg_instance is not None:
            with suppress(Exception):
                _kg_instance.close()
        _kg_instance = None
        logger.debug("KG singleton reset (test mode)")
