from __future__ import annotations

from typing import Any


class ActionExecutor:
    """Lightweight action executor used by the worker's LATS flow.

    The real system would call an LLM or toolchain per action, but for tests and
    offline execution we keep deterministic fallbacks.
    """

    def __init__(self, llm_provider: Any | None = None):
        """Initialize the action executor.

        Args:
            llm_provider: Optional LLM provider for generating responses.
        """
        self.llm_provider = llm_provider
        self.last_llm_usage: dict[str, Any] | None = None

    async def execute_action(
        self,
        *,
        action: str,
        text: str,
        max_length: int = 120,
        use_llm: bool = False,
    ) -> Any:
        """Run a simple action. When an LLM provider is available and requested, try.

        it; otherwise return a deterministic placeholder.
        """
        # Reset usage tracking per execution
        self.last_llm_usage = None

        action_name = action or "clean"
        base_text = (text or "").strip()

        if action_name.startswith("validate"):
            return {
                "type": action_name,
                "text": base_text[:max_length],
                "quality_score": 0.7,
            }

        if use_llm and self.llm_provider:
            try:
                response = await self.llm_provider.generate_content_async(
                    prompt=f"{action_name}: {base_text[:max_length]}",
                    max_output_tokens=max_length,
                    temperature=0,
                )
                self.last_llm_usage = getattr(response, "usage", None)
                return getattr(response, "content", base_text) or base_text
            except Exception:
                # Fallback to deterministic output if provider fails
                pass

        if action_name.startswith("clean"):
            return " ".join(base_text.split())[:max_length]

        return f"{action_name}:{base_text}"[:max_length]
