"""Features package - additional capabilities and enhancements."""
from typing import Any


def __getattr__(name: str) -> Any:
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
]
