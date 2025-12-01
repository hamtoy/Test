"""Routing package - request routing and graph-based routing."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import of routing module components.

    Args:
        name: The attribute name to retrieve.

    Returns:
        The GraphEnhancedRouter class.

    Raises:
        AttributeError: If name is not a valid module attribute.
    """
    if name == "GraphEnhancedRouter":
        from src.routing.graph_router import GraphEnhancedRouter

        return GraphEnhancedRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["GraphEnhancedRouter"]
