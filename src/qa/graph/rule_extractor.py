"""Rule extraction and QA generation module.

Provides methods for extracting rules from the knowledge graph
and generating QA pairs based on those rules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.qa.graph.connection import Neo4jConnectionManager
    from src.qa.graph.vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


class RuleExtractor:
    """Extracts rules and generates QA from knowledge graph.

    Provides methods for retrieving rules, constraints, and examples
    from the Neo4j knowledge graph for QA generation.

    Args:
        connection_manager: Neo4j connection manager
        vector_engine: Vector search engine for similarity queries
    """

    def __init__(
        self,
        connection_manager: Neo4jConnectionManager,
        vector_engine: VectorSearchEngine,
    ) -> None:
        """Initialize rule extractor."""
        self.connection = connection_manager
        self.vector_engine = vector_engine

    def get_rules_for_topic(self, topic: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get rules related to a specific topic.

        Args:
            topic: Topic to search for
            limit: Maximum number of rules to return

        Returns:
            List of rules with their constraints and examples
        """
        query = """
        MATCH (r:Rule)-[:HAS_CONSTRAINT]->(c:Constraint)
        OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example)
        WHERE r.topic CONTAINS $topic OR r.content CONTAINS $topic
        RETURN r.id AS rule_id,
               r.content AS rule_content,
               collect(DISTINCT c.content) AS constraints,
               collect(DISTINCT e.content) AS examples
        LIMIT $limit
        """

        try:
            results = self.connection.execute_query(
                query,
                {"topic": topic, "limit": limit},
            )
            return results
        except Exception as e:
            logger.warning("Failed to get rules for topic '%s': %s", topic, e)
            return []

    def get_similar_rules(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Get rules similar to the query using vector search.

        Args:
            query: Query text
            k: Number of rules to return

        Returns:
            List of similar rules with scores
        """
        return self.vector_engine.search_similar(query, k=k)

    def generate_qa_context(
        self,
        query: str,
        max_rules: int = 5,
        include_examples: bool = True,
    ) -> str:
        """Generate context for QA based on relevant rules.

        Args:
            query: User query
            max_rules: Maximum rules to include
            include_examples: Whether to include examples

        Returns:
            Formatted context string for QA generation
        """
        rules = self.get_similar_rules(query, k=max_rules)

        if not rules:
            return ""

        context_parts = ["## Relevant Rules\n"]

        for i, rule in enumerate(rules, 1):
            content = rule.get("content", "")
            metadata = rule.get("metadata", {})

            context_parts.append(f"### Rule {i}")
            context_parts.append(content)

            if include_examples and "examples" in metadata:
                context_parts.append("\n**Examples:**")
                context_parts.extend(
                    f"- {example}" for example in metadata["examples"][:2]
                )

            context_parts.append("")

        return "\n".join(context_parts)

    def validate_answer_against_rules(
        self,
        answer: str,
        query: str,
    ) -> dict[str, Any]:
        """Validate an answer against relevant rules.

        Args:
            answer: Answer to validate
            query: Original query

        Returns:
            Validation result with any rule violations
        """
        rules = self.get_similar_rules(query, k=3)

        # Note: This is a simplified validation placeholder.
        # Full implementation would require more sophisticated rule matching.
        violations: list[str] = []

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "rules_checked": len(rules),
        }
