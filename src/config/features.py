"""Feature Flags Configuration Settings.

Handles RAG, LATS, Data2Neo, and provider selection options.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class FeatureSettingsMixin(BaseSettings):
    """Feature flags and optional functionality (Mixin).

    Handles RAG, LATS, Data2Neo, and provider selection.
    """

    enable_rag: bool = Field(False, alias="ENABLE_RAG")
    enable_lats: bool = Field(False, alias="ENABLE_LATS")
    enable_data2neo: bool = Field(False, alias="ENABLE_DATA2NEO")
    enable_metrics: bool = Field(True, alias="ENABLE_METRICS")
    llm_provider_type: str = Field(
        "gemini",
        description="LLM provider type (gemini, etc.)",
    )
    graph_provider_type: str = Field(
        "neo4j",
        description="Graph provider type (neo4j, etc.)",
    )
    data2neo_batch_size: int = Field(100, alias="DATA2NEO_BATCH_SIZE")
    data2neo_confidence: float = Field(0.7, alias="DATA2NEO_CONFIDENCE_THRESHOLD")
