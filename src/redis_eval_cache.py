"""Backward compatibility - use src.caching.redis_cache instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.redis_eval_cache' is deprecated. "
        "Use 'from src.caching.redis_cache import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.caching import redis_cache

    return getattr(redis_cache, name)


def __dir__():
    from src.caching import redis_cache

    return dir(redis_cache)
