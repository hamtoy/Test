"""Q&A System package - question answering and RAG systems."""

from typing import Any

__all__ = [
    "QAKnowledgeGraph",
    "QASystemFactory",
    "IntegratedQAPipeline",
    "IntegratedQualitySystem",
    "MemoryAugmentedQASystem",
    "MultiAgentQASystem",
    "ExperimentResult",
    "ExperimentConfig",
    "PromptExperimentManager",
    "validate_constraints",
]


def __getattr__(name: str) -> Any:
    """Lazy import to avoid circular dependencies."""
    if name == "QAKnowledgeGraph":
        from src.qa.rag_system import QAKnowledgeGraph

        return QAKnowledgeGraph
    elif name == "QASystemFactory":
        from src.qa.factory import QASystemFactory

        return QASystemFactory
    elif name == "IntegratedQAPipeline":
        from src.qa.pipeline import IntegratedQAPipeline

        return IntegratedQAPipeline
    elif name == "IntegratedQualitySystem":
        from src.qa.quality import IntegratedQualitySystem

        return IntegratedQualitySystem
    elif name == "MemoryAugmentedQASystem":
        from src.qa.memory_augmented import MemoryAugmentedQASystem

        return MemoryAugmentedQASystem
    elif name == "MultiAgentQASystem":
        from src.qa.multi_agent import MultiAgentQASystem

        return MultiAgentQASystem
    elif name in ("ExperimentResult", "ExperimentConfig", "PromptExperimentManager"):
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
    elif name == "validate_constraints":
        from src.qa.validator import validate_constraints

        return validate_constraints
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
