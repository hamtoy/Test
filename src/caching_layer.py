"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.caching.layer' instead. Will be removed in v3.0.
"""

from typing import Any

from src._deprecation import warn_deprecated

# Emit warning immediately on module import
warn_deprecated(
    old_path="src.caching_layer",
    new_path="src.caching.layer",
    removal_version="v3.0",
)


def __getattr__(name: str) -> Any:
    # Also warn when accessing specific attributes
    from src.caching import layer

    return getattr(layer, name)


def __dir__() -> list[str]:
    from src.caching import layer

    return dir(layer)
