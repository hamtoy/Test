# src/infra/neo4j_optimizer.py
"""Neo4j 2-Tier Index Architecture implementation.
Optimizes query performance through dual-layer indexing.
"""

import re
from typing import Any, Dict, List, Optional
import logging

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

# Pattern to extract index name from CREATE [VECTOR] INDEX statements
_INDEX_NAME_PATTERN = re.compile(r"CREATE\s+(?:VECTOR\s+)?INDEX\s+(\w+)", re.IGNORECASE)


class TwoTierIndexManager:
    """Manages 2-Tier indexing strategy for Neo4j:
    - Tier 1: Object indexing (node properties)
    - Tier 2: Triad indexing (relationship patterns)
    """

    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    async def create_all_indexes(self) -> None:
        """Create both tiers of indexes."""
        await self.create_object_indexes()
        await self.create_triad_indexes()
        logger.info("2-Tier index architecture created successfully")

    # ============ TIER 1: Object Indexes ============

    async def create_object_indexes(self) -> None:
        """Create 1st tier indexes on node properties.
        Optimizes single-node lookups.
        """
        queries = [
            # Rule node indexes
            """
            CREATE INDEX rule_id_idx IF NOT EXISTS
            FOR (r:Rule) ON (r.id)
            """,
            """
            CREATE INDEX rule_type_idx IF NOT EXISTS
            FOR (r:Rule) ON (r.type)
            """,
            """
            CREATE INDEX rule_composite_idx IF NOT EXISTS
            FOR (r:Rule) ON (r.id, r.type)
            """,
            # RuleExtraction node index
            """
            CREATE INDEX extraction_id_idx IF NOT EXISTS
            FOR (e:RuleExtraction) ON (e.id)
            """,
            # Document node indexes
            """
            CREATE INDEX document_id_idx IF NOT EXISTS
            FOR (d:Document) ON (d.id)
            """,
            """
            CREATE INDEX document_title_idx IF NOT EXISTS
            FOR (d:Document) ON (d.title)
            """,
            # Chunk node indexes (for Vector Search)
            """
            CREATE INDEX chunk_id_idx IF NOT EXISTS
            FOR (c:Chunk) ON (c.id)
            """,
            # Vector index for embedding similarity search.
            # Note: Backticks around property names are Neo4j's required syntax
            # for index configuration options (not JSON).
            """
            CREATE VECTOR INDEX chunk_embedding_idx IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 768,
                    `vector.similarity_function`: 'cosine'
                }
            }
            """,
        ]

        for query in queries:
            await self._execute_query(query)
            index_name = self._extract_index_name(query)
            logger.info("Created index: %s", index_name)

    # ============ TIER 2: Triad Indexes ============

    async def create_triad_indexes(self) -> None:
        """Create 2nd tier indexes on relationship patterns.
        Optimizes graph traversal queries.

        Triad format: (subject)-[predicate]->(object)
        """
        queries = [
            # Document-Rule relationship index
            """
            CREATE INDEX triad_document_rule_idx IF NOT EXISTS
            FOR ()-[r:DOCUMENT_RULE]->()
            ON (r.document_id, r.rule_id)
            """,
            # EXTRACTED_FROM relationship index
            """
            CREATE INDEX triad_extracted_from_idx IF NOT EXISTS
            FOR ()-[r:EXTRACTED_FROM]->()
            ON (r.extraction_id, r.document_id)
            """,
            # HAS_CHUNK relationship index
            """
            CREATE INDEX triad_has_chunk_idx IF NOT EXISTS
            FOR ()-[r:HAS_CHUNK]->()
            ON (r.document_id, r.chunk_id)
            """,
            # RELATES_TO relationship index (rule-to-rule associations)
            """
            CREATE INDEX triad_relates_to_idx IF NOT EXISTS
            FOR ()-[r:RELATES_TO]->()
            ON (r.source_rule_id, r.target_rule_id, r.relation_type)
            """,
        ]

        for query in queries:
            await self._execute_query(query)
            index_name = self._extract_index_name(query)
            logger.info("Created triad index: %s", index_name)

    # ============ Index Management ============

    async def list_all_indexes(self) -> List[Dict[str, Any]]:
        """List all existing indexes."""
        query = "SHOW INDEXES"
        records = await self._execute_query(query)
        return [dict(record) for record in records]

    async def analyze_index_usage(self) -> Dict[str, Any]:
        """Analyze index usage statistics.
        Returns query performance metrics.
        """
        query = """
        CALL db.stats.retrieve('QUERIES')
        YIELD data
        RETURN data
        """
        records = await self._execute_query(query)
        return records[0]["data"] if records else {}

    async def drop_all_indexes(self) -> None:
        """Drop all indexes (use with caution!)."""
        indexes = await self.list_all_indexes()
        for idx in indexes:
            if idx.get("type") != "LOOKUP":  # Skip system indexes
                query = f"DROP INDEX {idx['name']} IF EXISTS"
                await self._execute_query(query)
                logger.warning("Dropped index: %s", idx["name"])

    # ============ Helper Methods ============

    @staticmethod
    def _extract_index_name(query: str) -> str:
        """Extract index name from a CREATE INDEX query.

        Handles both 'CREATE INDEX name' and 'CREATE VECTOR INDEX name' formats.

        Args:
            query: The Cypher CREATE INDEX query string.

        Returns:
            The extracted index name or 'unknown' if not found.
        """
        match = _INDEX_NAME_PATTERN.search(query)
        return match.group(1) if match else "unknown"

    async def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute Cypher query and return results."""
        async with self.driver.session() as session:
            result = await session.run(query)
            data: List[Dict[str, Any]] = await result.data()
            return data


# ============ Optimized Query Examples ============


class OptimizedQueries:
    """Example queries that benefit from 2-Tier indexing.
    """

    @staticmethod
    def find_rules_by_document(_document_id: Optional[str] = None) -> str:
        """Find all rules associated with a document.
        Uses: rule_id_idx + triad_document_rule_idx

        Args:
            _document_id: Optional document ID (for documentation only,
                         the actual value should be passed as a parameter).

        Returns:
            Cypher query string with $document_id parameter placeholder.
        """
        return """
        MATCH (d:Document {id: $document_id})-[r:DOCUMENT_RULE]->(rule:Rule)
        RETURN rule.id, rule.type, rule.content
        """

    @staticmethod
    def find_related_rules(_rule_id: Optional[str] = None, max_depth: int = 2) -> str:
        """Find rules related to a given rule (transitive closure).
        Uses: triad_relates_to_idx

        Args:
            _rule_id: Optional rule ID (for documentation only,
                     the actual value should be passed as a parameter).
            max_depth: Maximum traversal depth (default: 2).

        Returns:
            Cypher query string with $rule_id parameter placeholder.
        """
        return f"""
        MATCH path = (r1:Rule {{id: $rule_id}})-[:RELATES_TO*1..{max_depth}]->(r2:Rule)
        RETURN r2.id, r2.type, length(path) as distance
        ORDER BY distance
        """

    @staticmethod
    def semantic_search_with_graph(
        _embedding: Optional[List[float]] = None, _k: int = 10
    ) -> str:
        """Hybrid search: Vector similarity + Graph traversal.
        Uses: chunk_embedding_idx + triad_has_chunk_idx

        Args:
            _embedding: Optional embedding vector (for documentation only,
                       the actual value should be passed as a parameter).
            _k: Number of top results to return (default: 10).

        Returns:
            Cypher query string with $k and $embedding parameter placeholders.
        """
        return """
        CALL db.index.vector.queryNodes('chunk_embedding_idx', $k, $embedding)
        YIELD node as chunk, score
        MATCH (chunk)<-[:HAS_CHUNK]-(doc:Document)-[:DOCUMENT_RULE]->(rule:Rule)
        RETURN rule.id, rule.content, doc.title, score
        ORDER BY score DESC
        """
