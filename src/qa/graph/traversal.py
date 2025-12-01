"""Graph traversal utilities for Neo4j knowledge graph.

Provides methods for traversing and querying the knowledge graph
structure, including descendant discovery and relationship walking.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphTraversal:
    """Traverses Neo4j knowledge graph for QA operations.
    
    Provides methods to walk relationships, find descendants,
    and discover connected concepts in the graph.
    
    Args:
        query_executor: QueryExecutor instance for graph queries
    """
    
    def __init__(self, query_executor: Any) -> None:
        """Initialize the graph traversal."""
        self._executor = query_executor
    
    def get_descendants(
        self,
        node_id: str,
        node_label: str = "Concept",
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find all descendants of a node up to max_depth.
        
        Args:
            node_id: The ID of the starting node
            node_label: The label of the node type
            max_depth: Maximum traversal depth
            
        Returns:
            List of descendant nodes with their properties
        """
        cypher = f"""
        MATCH (start:{node_label} {{id: $node_id}})
        MATCH path = (start)-[*1..{max_depth}]->(descendant)
        RETURN DISTINCT
            descendant.id AS id,
            labels(descendant)[0] AS label,
            descendant.name AS name,
            length(path) AS depth
        ORDER BY depth, id
        """
        
        try:
            return self._executor.execute(cypher, {"node_id": node_id})
        except Exception as e:
            logger.warning("Failed to get descendants for %s: %s", node_id, e)
            return []
    
    def find_path_between(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 5,
    ) -> Optional[List[Dict[str, Any]]]:
        """Find the shortest path between two nodes.
        
        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_hops: Maximum number of hops to search
            
        Returns:
            List of nodes in the path, or None if no path found
        """
        cypher = f"""
        MATCH path = shortestPath(
            (start {{id: $start_id}})-[*1..{max_hops}]-(end {{id: $end_id}})
        )
        UNWIND nodes(path) AS node
        RETURN 
            node.id AS id,
            labels(node)[0] AS label,
            node.name AS name
        """
        
        try:
            results = self._executor.execute(
                cypher, 
                {"start_id": start_id, "end_id": end_id}
            )
            return results if results else None
        except Exception as e:
            logger.warning("Path finding failed: %s", e)
            return None
    
    def get_connected_concepts(
        self,
        concept_id: str,
        relationship_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all concepts connected to a given concept.
        
        Args:
            concept_id: The concept node ID
            relationship_types: Optional filter for relationship types
            
        Returns:
            List of connected concept nodes
        """
        rel_filter = ""
        if relationship_types:
            rel_types = "|".join(relationship_types)
            rel_filter = f"[:{rel_types}]"
        
        cypher = f"""
        MATCH (c:Concept {{id: $concept_id}})-{rel_filter}-(connected)
        RETURN DISTINCT
            connected.id AS id,
            labels(connected)[0] AS label,
            connected.name AS name,
            connected.description AS description
        """
        
        try:
            return self._executor.execute(cypher, {"concept_id": concept_id})
        except Exception as e:
            logger.warning("Failed to get connected concepts: %s", e)
            return []
    
    def count_relationships(
        self,
        node_id: str,
        direction: str = "both",
    ) -> Dict[str, int]:
        """Count relationships by type for a node.
        
        Args:
            node_id: The node ID to analyze
            direction: 'in', 'out', or 'both'
            
        Returns:
            Dictionary mapping relationship types to counts
        """
        if direction == "in":
            pattern = "(n)<-[r]-()"
        elif direction == "out":
            pattern = "(n)-[r]->()"
        else:
            pattern = "(n)-[r]-()"
        
        cypher = f"""
        MATCH {pattern}
        WHERE n.id = $node_id
        RETURN type(r) AS rel_type, count(r) AS count
        """
        
        try:
            results = self._executor.execute(cypher, {"node_id": node_id})
            return {r["rel_type"]: r["count"] for r in results}
        except Exception as e:
            logger.warning("Relationship counting failed: %s", e)
            return {}


def create_traversal(query_executor: Any) -> GraphTraversal:
    """Factory function to create a GraphTraversal.
    
    Args:
        query_executor: QueryExecutor instance for graph queries
        
    Returns:
        Configured GraphTraversal instance
    """
    return GraphTraversal(query_executor)
