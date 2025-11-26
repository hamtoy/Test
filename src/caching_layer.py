"""Backward compatibility - use src.caching.layer instead."""

import warnings
from typing import Any


def __getattr__(name: str) -> Any:
    warnings.warn(
        f"Importing '{name}' from 'src.caching_layer' is deprecated. "
        "Use 'from src.caching.layer import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.caching import layer

    return getattr(layer, name)


def __dir__() -> list[str]:
    from src.caching import layer

    return dir(layer)
