"""Analytics package - usage pattern analysis and reporting."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import of analytics module components.

    Args:
        name: The attribute name to retrieve.

    Returns:
        The UsageDashboard class if name matches.

    Raises:
        AttributeError: If name is not a valid module attribute.
    """
    if name == "UsageDashboard":
        from src.analytics.dashboard import UsageDashboard

        return UsageDashboard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "UsageDashboard",
]
