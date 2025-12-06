"""Rule management operations for Neo4j graph database.

Provides CRUD operations for rules with automatic cache invalidation.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator
from uuid import uuid4

from src.qa.rule_loader import clear_global_rule_cache

logger = logging.getLogger(__name__)


class RuleManager:
    """Manages rule CRUD operations with cache invalidation.
    
    Handles create, update, and delete operations for rules in Neo4j,
    ensuring cache is invalidated after each mutation.
    """
    
    def __init__(self, graph_session_func: Any):
        """Initialize rule manager.
        
        Args:
            graph_session_func: Function that returns a graph session context manager
        """
        self.graph_session = graph_session_func
    
    def update_rule(self, rule_id: str, new_text: str) -> None:
        """Update rule text and invalidate cache.
        
        Args:
            rule_id: Rule ID to update
            new_text: New rule text
        """
        cypher = """
        MATCH (r:Rule {id: $rule_id})
        SET r.text = $new_text
        RETURN count(r) AS updated
        """
        with self.graph_session() as session:
            if session is None:
                logger.warning("update_rule skipped: graph unavailable")
                return
            result = session.run(cypher, rule_id=rule_id, new_text=new_text)
            updated = result.single().get("updated", 0) if result else 0
            logger.info("Rule updated id=%s (updated=%s)", rule_id, updated)
        
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after update")
    
    def add_rule(self, query_type: str, rule_text: str) -> str:
        """Add new rule and invalidate cache.
        
        Args:
            query_type: Query type to associate with
            rule_text: Rule text content
            
        Returns:
            Created rule ID
        """
        rule_id = str(uuid4())
        cypher = """
        MERGE (qt:QueryType {name: $query_type})
        CREATE (r:Rule {id: $rule_id, text: $rule_text})
        MERGE (r)-[:APPLIES_TO]->(qt)
        RETURN r.id AS id
        """
        with self.graph_session() as session:
            if session is None:
                logger.warning("add_rule skipped: graph unavailable")
                return rule_id
            result = session.run(
                cypher, query_type=query_type, rule_id=rule_id, rule_text=rule_text
            )
            record = result.single() if result else None
            created_id = record.get("id") if record else rule_id
            logger.info("Rule added id=%s (query_type=%s)", created_id, query_type)
            rule_id = str(created_id)
        
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after add")
        return rule_id
    
    def delete_rule(self, rule_id: str) -> None:
        """Delete rule and invalidate cache.
        
        Args:
            rule_id: Rule ID to delete
        """
        cypher = "MATCH (r:Rule {id: $rule_id}) DETACH DELETE r"
        with self.graph_session() as session:
            if session is None:
                logger.warning("delete_rule skipped: graph unavailable")
                return
            result = session.run(cypher, rule_id=rule_id)
            summary = result.consume() if result else None
            deleted = getattr(summary.counters, "nodes_deleted", 0) if summary else 0
            logger.info("Rule deleted id=%s (deleted=%s)", rule_id, deleted)
        
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after delete")
