"""Features package - additional capabilities and enhancements."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import of feature module components.

    Args:
        name: The attribute name to retrieve.

    Returns:
        The requested feature class or function.

    Raises:
        AttributeError: If name is not a valid module attribute.
    """
    if name == "SmartAutocomplete":
        from src.features.autocomplete import SmartAutocomplete

        return SmartAutocomplete
    if name == "MultimodalUnderstanding":
        from src.features.multimodal import MultimodalUnderstanding

        return MultimodalUnderstanding
    if name == "SelfCorrectingChain":
        from src.features.self_correcting import SelfCorrectingQAChain

        return SelfCorrectingQAChain
    if name == "SelfCorrectingQAChain":
        from src.features.self_correcting import SelfCorrectingQAChain

        return SelfCorrectingQAChain
    if name == "LATSSearcher":
        from src.features.lats import LATSSearcher

        return LATSSearcher
    if name == "AdaptiveDifficulty":
        from src.features.difficulty import AdaptiveDifficultyAdjuster

        return AdaptiveDifficultyAdjuster
    if name == "AdaptiveDifficultyAdjuster":
        from src.features.difficulty import AdaptiveDifficultyAdjuster

        return AdaptiveDifficultyAdjuster
    if name == "ActionExecutor":
        from src.features.action_executor import ActionExecutor

        return ActionExecutor
    if name == "Data2NeoExtractor":
        from src.features.data2neo_extractor import Data2NeoExtractor

        return Data2NeoExtractor
    if name == "create_data2neo_extractor":
        from src.features.data2neo_extractor import create_data2neo_extractor

        return create_data2neo_extractor
    if name == "SelfImprovingSystem":
        from src.features.self_improvement import SelfImprovingSystem

        return SelfImprovingSystem
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SmartAutocomplete",
    "MultimodalUnderstanding",
    "SelfCorrectingChain",
    "SelfCorrectingQAChain",
    "LATSSearcher",
    "AdaptiveDifficulty",
    "AdaptiveDifficultyAdjuster",
    "ActionExecutor",
    "Data2NeoExtractor",
    "create_data2neo_extractor",
    "SelfImprovingSystem",
]
