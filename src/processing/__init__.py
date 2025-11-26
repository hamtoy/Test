"""Processing package - data loading and processing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.processing.loader import load_input_data, reload_data_if_needed
    from src.processing.template_generator import DynamicTemplateGenerator
    from src.processing.example_selector import DynamicExampleSelector
    from src.processing.context_augmentation import AdvancedContextAugmentation


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid circular imports."""
    if name == "load_input_data":
        from src.processing.loader import load_input_data

        return load_input_data
    if name == "reload_data_if_needed":
        from src.processing.loader import reload_data_if_needed

        return reload_data_if_needed
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
    "load_input_data",
    "reload_data_if_needed",
    "DynamicTemplateGenerator",
    "DynamicExampleSelector",
    "AdvancedContextAugmentation",
]
