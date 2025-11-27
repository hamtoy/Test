"""Backward compatibility - use src.caching.layer instead."""

import warnings
from typing import Any

# Emit warning immediately on module import
warnings.warn(
    "Importing from 'src.caching_layer' is deprecated. "
    "Use 'from src.caching.layer import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    # Also warn when accessing specific attributes
    from src.caching import layer

    return getattr(layer, name)


def __dir__() -> list[str]:
    from src.caching import layer

    return dir(layer)
