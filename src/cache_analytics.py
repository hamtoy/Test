"""Backward compatibility - use src.caching.analytics instead."""

import warnings


def __getattr__(name: str) -> object:
    warnings.warn(
        f"Importing '{name}' from 'src.cache_analytics' is deprecated. "
        "Use 'from src.caching.analytics import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.caching import analytics

    return getattr(analytics, name)


def __dir__() -> list[str]:
    from src.caching import analytics

    return dir(analytics)
