"""LLM package - language model clients and chains."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.llm.gemini import GeminiModelClient
    from src.llm.langchain_system import UltimateLangChainQASystem
    from src.llm.lcel_chain import LCELOptimizedChain


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid circular imports."""
    if name == "GeminiModelClient":
        from src.llm.gemini import GeminiModelClient

        return GeminiModelClient
    if name == "UltimateLangChainQASystem":
        from src.llm.langchain_system import UltimateLangChainQASystem

        return UltimateLangChainQASystem
    if name == "LCELOptimizedChain":
        from src.llm.lcel_chain import LCELOptimizedChain

        return LCELOptimizedChain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "GeminiModelClient",
    "LCELOptimizedChain",
    "UltimateLangChainQASystem",
]
