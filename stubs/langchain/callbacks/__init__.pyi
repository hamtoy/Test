"""
Type stubs for langchain.callbacks module.
"""

from typing import Any, Dict, List

class BaseCallbackHandler:
    """Base callback handler type stub."""

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None: ...
    def on_llm_end(self, response: Any, **kwargs: Any) -> None: ...
    def on_chain_error(self, error: Exception, **kwargs: Any) -> None: ...

__all__ = ["BaseCallbackHandler"]
