"""Common type aliases for the project.

Using type aliases improves readability and consistency across the codebase.
"""

from typing import Any, Protocol, runtime_checkable


# JSON-like structures
JsonDict = dict[str, Any]
JsonList = list[Any]

# Common collections
StringList = list[str]
StringDict = dict[str, str]
IntList = list[int]

# Nested structures
NestedDict = dict[str, dict[str, Any]]
NestedList = list[list[str]]


# =============================================================================
# Protocols for external modules (type safety without tight coupling)
# =============================================================================


@runtime_checkable
class CachedContentProtocol(Protocol):
    """Protocol for cached content objects (e.g., google.generativeai.caching.CachedContent).

    Defines the minimal interface required for cached content handling.
    """

    @property
    def name(self) -> str:
        """Name/identifier of the cached content."""
        ...

    def delete(self) -> None:
        """Delete/invalidate the cached content."""
        ...


class CachedContentAccessProtocol(Protocol):
    """Protocol for CachedContent class access (e.g., caching_module.CachedContent).

    Defines the interface for retrieving cached content by name.
    """

    @staticmethod
    def get(*, name: str) -> CachedContentProtocol:
        """Retrieve cached content by name.

        Args:
            name: The name/identifier of the cached content.

        Returns:
            The cached content object.
        """
        ...


class CachingModuleProtocol(Protocol):
    """Protocol for caching module (e.g., google.generativeai.caching).

    Defines the minimal interface for cache retrieval operations.
    """

    @property
    def CachedContent(self) -> type[CachedContentAccessProtocol]:
        """Access to the CachedContent class."""
        ...


__all__ = [
    "JsonDict",
    "JsonList",
    "StringList",
    "StringDict",
    "IntList",
    "NestedDict",
    "NestedList",
    "CachedContentProtocol",
    "CachingModuleProtocol",
    "CachedContentAccessProtocol",
]
