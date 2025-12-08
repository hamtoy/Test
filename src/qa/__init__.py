"""Q&A System package - question answering and RAG systems."""

from typing import Any

__all__ = [
    "ExperimentConfig",
    "ExperimentResult",
    "IntegratedQAPipeline",
    "IntegratedQualitySystem",
    "MemoryAugmentedQASystem",
    "MultiAgentQASystem",
    "PromptExperimentManager",
    "QAKnowledgeGraph",
    "QASystemFactory",
    "validate_constraints",
]


def __getattr__(name: str) -> Any:
    """Lazy import to avoid circular dependencies."""
    if name == "QAKnowledgeGraph":
        from src.qa.rag_system import QAKnowledgeGraph

        return QAKnowledgeGraph
    if name == "QASystemFactory":
        from src.qa.factory import QASystemFactory

        return QASystemFactory
    if name == "IntegratedQAPipeline":
        from src.qa.pipeline import IntegratedQAPipeline

        return IntegratedQAPipeline
    if name == "IntegratedQualitySystem":
        from src.qa.quality import IntegratedQualitySystem

        return IntegratedQualitySystem
    if name == "MemoryAugmentedQASystem":
        from src.qa.memory_augmented import MemoryAugmentedQASystem

        return MemoryAugmentedQASystem
    if name == "MultiAgentQASystem":
        from src.qa.multi_agent import MultiAgentQASystem

        return MultiAgentQASystem
    if name in ("ExperimentResult", "ExperimentConfig", "PromptExperimentManager"):
        from src.qa.ab_test import (
            ExperimentConfig,
            ExperimentResult,
            PromptExperimentManager,
        )

        return {
            "ExperimentResult": ExperimentResult,
            "ExperimentConfig": ExperimentConfig,
            "PromptExperimentManager": PromptExperimentManager,
        }[name]
    if name == "validate_constraints":
        from src.qa.validator import validate_constraints

        return validate_constraints
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
