"""UI 패키지."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .panels import console, display_queries, render_budget_panel, render_cost_panel

if TYPE_CHECKING:
    from .interactive_menu import interactive_main


def __getattr__(name: str) -> Any:
    """Lazy import for interactive_main to avoid circular imports."""
    if name == "interactive_main":
        from .interactive_menu import interactive_main

        return interactive_main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "console",
    "render_cost_panel",
    "render_budget_panel",
    "display_queries",
    "interactive_main",
]
