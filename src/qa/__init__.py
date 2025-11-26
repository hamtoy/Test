"""Q&A System package - question answering and RAG systems."""

__all__ = [
    "QAKnowledgeGraph",
    "QASystemFactory",
    "IntegratedQAPipeline",
    "IntegratedQualitySystem",
    "MemoryAugmentedQASystem",
    "MultiAgentQASystem",
]


def __getattr__(name):
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
