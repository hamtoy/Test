"""Analysis router for standalone scripts.

Provides API endpoints for:
- Semantic topic extraction
- Document structure comparison
- Rule promotion from review logs
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)


@router.post("/semantic")
async def run_semantic_analysis(
    top_k: int = 30,
) -> dict[str, Any]:
    """Run semantic topic extraction and Neo4j linking.

    Extracts keywords from Block content and creates Topic nodes.

    Args:
        top_k: Number of top keywords to extract
    """
    import os

    from neo4j import GraphDatabase

    from src.analysis.semantic import (
        count_keywords,
        create_topics,
        fetch_blocks,
        link_blocks_to_topics,
    )

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        raise HTTPException(status_code=500, detail="Neo4j credentials not configured")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        blocks = fetch_blocks(driver)

        if not blocks:
            return {"status": "no_data", "message": "No blocks found"}

        contents = [b["content"] for b in blocks if b.get("content")]
        keyword_counter = count_keywords(contents)
        keywords = keyword_counter.most_common(top_k)

        create_topics(driver, keywords)
        link_blocks_to_topics(driver, blocks, keywords)
        driver.close()

        return {
            "status": "success",
            "topics_created": len(keywords),
            "blocks_processed": len(blocks),
            "top_keywords": keywords[:10],
        }
    except Exception as exc:
        logger.error("Semantic analysis failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/document-compare")
async def run_document_comparison(limit: int = 10) -> dict[str, Any]:
    """Compare document structures and find common content.

    Args:
        limit: Maximum number of common content items to return
    """
    import os

    from neo4j import GraphDatabase

    from src.analysis.document_compare import compare_structure, find_common_content

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        raise HTTPException(status_code=500, detail="Neo4j credentials not configured")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        structures = compare_structure(driver)
        commons = find_common_content(driver, limit=limit)
        driver.close()

        return {
            "status": "success",
            "structures": structures,
            "common_content": [
                {"content": content[:100], "pages": pages} for content, pages in commons
            ],
        }
    except Exception as exc:
        logger.error("Document comparison failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/promote-rules")
async def run_rule_promotion(days: int = 7) -> dict[str, Any]:
    """Analyze review logs and suggest new rules.

    Args:
        days: Number of days of logs to analyze
    """
    try:
        from src.automation.promote_rules import run_promote_rules

        rules = run_promote_rules(days=days)

        return {
            "status": "success",
            "rules_suggested": len(rules),
            "rules": rules,
        }
    except OSError as exc:
        logger.error("Rule promotion failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Rule promotion failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


__all__ = ["router"]
