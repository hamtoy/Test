from __future__ import annotations

from typing import Optional

from src.config import AppConfig
from src.core.adapters import GeminiProvider, Neo4jProvider
from src.core.interfaces import GraphProvider, LLMProvider


def get_llm_provider(config: AppConfig) -> LLMProvider:
    """
    Factory to create an LLM provider based on configuration.
    Defaults to GeminiProvider if not specified or if 'gemini' is selected.
    """
    provider_type = getattr(config, "llm_provider_type", "gemini").lower()

    if provider_type == "gemini":
        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiProvider")
        return GeminiProvider(
            api_key=config.api_key,
            model_name=config.model_name,
        )

    # Future extension:
    # elif provider_type == "openai":
    #     return OpenAIProvider(...)

    raise ValueError(f"Unsupported LLM provider type: {provider_type}")


def get_graph_provider(config: AppConfig) -> Optional[GraphProvider]:
    """
    Factory to create a Graph provider based on configuration.
    Defaults to Neo4jProvider if not specified or if 'neo4j' is selected.
    """
    provider_type = getattr(config, "graph_provider_type", "neo4j").lower()

    if provider_type == "neo4j":
        uri = getattr(config, "neo4j_uri", None)
        user = getattr(config, "neo4j_user", None)
        password = getattr(config, "neo4j_password", None)
        if not uri or not user or not password:
            return None
        return Neo4jProvider(
            uri=uri,
            auth=(user, password),
        )

    raise ValueError(f"Unsupported Graph provider type: {provider_type}")
