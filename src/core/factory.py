from __future__ import annotations


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


def get_graph_provider(config: AppConfig) -> GraphProvider:
    """
    Factory to create a Graph provider based on configuration.
    Defaults to Neo4jProvider if not specified or if 'neo4j' is selected.
    """
    provider_type = getattr(config, "graph_provider_type", "neo4j").lower()

    if provider_type == "neo4j":
        if not config.neo4j_uri or not config.neo4j_user or not config.neo4j_password:
            raise ValueError(
                "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are required for Neo4jProvider"
            )
        return Neo4jProvider(
            uri=config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password),
        )

    raise ValueError(f"Unsupported Graph provider type: {provider_type}")
