"""Common type aliases for the project.

Using type aliases improves readability and consistency across the codebase.
"""

from typing import Any

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

__all__ = [
    "JsonDict",
    "JsonList",
    "StringList",
    "StringDict",
    "IntList",
    "NestedDict",
    "NestedList",
]
