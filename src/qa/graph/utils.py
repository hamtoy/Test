"""Graph-related helper utilities for the QA knowledge graph."""

from __future__ import annotations

import logging
import os
from collections.abc import Sized
from typing import Any, cast

import google.generativeai as genai
from langchain_core.exceptions import LangChainException
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.caching.analytics import CacheMetrics
from src.core.interfaces import GraphProvider
from src.infra.neo4j import SafeDriver
from src.infra.utils import run_async_safely


def len_if_sized(obj: Any) -> int:
    """Return len(obj) when supported, otherwise 0."""
    if isinstance(obj, Sized):
        return len(obj)
    return 0


class CustomGeminiEmbeddings:
    """Gemini 임베딩 래퍼."""

    def __init__(self, api_key: str, model: str = "models/text-embedding-004") -> None:
        """Initialize the Gemini embeddings wrapper."""
        genai_any = cast("Any", genai)
        genai_any.configure(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        genai_any = cast("Any", genai)
        result = genai_any.embed_content(
            model=self.model, content=text, task_type="retrieval_query",
        )
        return list(result["embedding"])


def init_vector_store(
    *,
    neo4j_uri: str | None,
    neo4j_user: str | None,
    neo4j_password: str | None,
    logger: logging.Logger,
) -> Any:
    """Initialize Neo4j vector store if embedding key is available."""
    try:
        from langchain_neo4j import Neo4jVector
    except ImportError as exc:
        logger.debug("langchain_neo4j not installed; skipping vector store. (%s)", exc)
        return None

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.debug("GEMINI_API_KEY not set; skipping vector store initialization.")
        return None

    try:
        embedding_model: Any = CustomGeminiEmbeddings(api_key=gemini_api_key)
        return Neo4jVector.from_existing_graph(
            embedding_model,
            url=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            index_name="rule_embeddings",
            node_label="Rule",
            text_node_properties=["text", "section"],
            embedding_node_property="embedding",
        )
    except (Neo4jError, ServiceUnavailable, LangChainException, ValueError) as exc:
        logger.warning("Failed to initialize Neo4j vector store: %s", exc)
        return None


def ensure_formatting_rule_schema(
    *,
    driver: SafeDriver | None,
    provider: GraphProvider | None,
    logger: logging.Logger,
) -> None:
    """Ensure FormattingRule schema and default node exist."""
    statements = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (fr:FormattingRule) REQUIRE fr.name IS UNIQUE",
        """
        MERGE (fr:FormattingRule {name: 'default'})
        SET fr.applies_to = 'all',
            fr.description = 'Default formatting rule',
            fr.priority = 0,
            fr.category = 'general',
            fr.examples_good = '',
            fr.examples_bad = ''
        """,
    ]

    if driver is not None:
        raw_driver = getattr(driver, "driver", None)
        if raw_driver is not None and hasattr(raw_driver, "session"):
            try:
                with driver.session() as session:
                    for stmt in statements:
                        session.run(stmt)
                return
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("FormattingRule schema ensure failed (sync): %s", exc)
        else:
            logger.info("Skip FormattingRule schema ensure: driver has no session()")

    if provider is None:
        logger.info("Skipping FormattingRule schema ensure; no graph provider")
        return

    async def _run() -> None:
        try:
            async with provider.session() as session:
                for stmt in statements:
                    await session.run(stmt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("FormattingRule schema ensure failed (async): %s", exc)

    run_async_safely(_run())


def record_vector_metrics(
    cache_metrics: CacheMetrics,
    *,
    query: str,
    k: int,
    result_count: int,
    success: bool,
    duration_ms: float,
) -> dict[str, Any]:
    """Record vector search metrics and build structured extras."""
    status = "hit" if success else "error"
    cache_metrics.record_query(
        "vector_search",
        duration_ms=duration_ms,
        result_count=result_count,
        status=status,
    )
    return {
        "metric": "vector_search",
        "duration_ms": round(duration_ms, 2),
        "k": k,
        "query_length": len(query),
        "result_count": result_count,
    }


def format_rules(rules_data: list[dict[str, Any]]) -> str:
    """Format rules data into markdown structure."""
    if not rules_data:
        return ""

    rules_texts = [rule.get("text", "") for rule in rules_data if rule.get("text")]
    if not rules_texts:
        return ""
    lines = ["### Formatting Rules"]
    lines.extend(f"- {text}" for text in rules_texts)
    return "\n".join(lines)
