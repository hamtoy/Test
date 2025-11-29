"""Analytics package - usage pattern analysis and reporting."""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "UsageDashboard":
        from src.analytics.dashboard import UsageDashboard

        return UsageDashboard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "UsageDashboard",
]
