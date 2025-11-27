"""
Partial type stubs for langchain.

Only commonly used classes are stubbed to enable strict type checking.
"""

from typing import Any, Optional

class Document:
    """Langchain Document type stub."""

    page_content: str
    metadata: dict[str, Any]

    def __init__(
        self,
        page_content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None: ...

class BaseRetriever:
    """Base retriever type stub."""

    def get_relevant_documents(self, query: str) -> list[Document]: ...
    async def aget_relevant_documents(self, query: str) -> list[Document]: ...

__all__ = ["Document", "BaseRetriever"]
