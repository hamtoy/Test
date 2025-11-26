"""Processing package - data loading and processing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.processing.loader import DataLoader
    from src.processing.template_generator import DynamicTemplateGenerator
    from src.processing.example_selector import DynamicExampleSelector
    from src.processing.context_augmentation import AdvancedContextAugmentation


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid circular imports."""
    if name == "DataLoader":
        from src.processing.loader import DataLoader
        return DataLoader
    if name == "DynamicTemplateGenerator":
        from src.processing.template_generator import DynamicTemplateGenerator
        return DynamicTemplateGenerator
    if name == "DynamicExampleSelector":
        from src.processing.example_selector import DynamicExampleSelector
        return DynamicExampleSelector
    if name == "AdvancedContextAugmentation":
        from src.processing.context_augmentation import AdvancedContextAugmentation
        return AdvancedContextAugmentation
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DataLoader",
    "DynamicTemplateGenerator",
    "DynamicExampleSelector",
    "AdvancedContextAugmentation",
]
