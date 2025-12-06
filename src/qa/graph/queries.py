"""Cypher query repository for Neo4j graph operations.

Centralized storage of all Cypher queries used by the RAG system.
"""

from __future__ import annotations


class CypherQueries:
    """Repository of Cypher queries for graph operations."""
    
    # Constraint queries
    GET_CONSTRAINTS_FOR_QUERY_TYPE = """
        // 1. QueryType 연결 Constraint
        MATCH (qt:QueryType {name: $qt})-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN 
            c.id AS id,
            c.type AS type,
            c.description AS description,
            c.pattern AS pattern,
            c.severity AS severity,
            c.max_repetition AS max_repetition,
            c.rules AS rules,
            c.priority AS priority,
            c.category AS category,
            c.applies_to AS applies_to
        
        UNION
        
        // 2. 피드백 기반 Constraint
        MATCH (c:Constraint)
        WHERE c.source STARTS WITH 'feedback_'
        RETURN 
            c.id AS id,
            c.type AS type,
            c.description AS description,
            c.pattern AS pattern,
            c.severity AS severity,
            c.max_repetition AS max_repetition,
            c.rules AS rules,
            c.priority AS priority,
            c.category AS category,
            c.applies_to AS applies_to
        """
    
    # Rule queries
    GET_RULES_FOR_QUERY_TYPE = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (r:Rule)-[:APPLIES_TO]->(qt)
        WITH qt, collect(r) AS rules_rel
        
        OPTIONAL MATCH (r2:Rule)
        WHERE r2.applies_to IN ['all', $qt]
        WITH qt, rules_rel, collect(r2) AS rules_attr
        
        OPTIONAL MATCH (r3:Rule)
        WHERE r3.source = 'feedback_analysis'
        WITH
            qt,
            coalesce(rules_rel, []) AS rules_rel,
            coalesce(rules_attr, []) AS rules_attr,
            collect(r3) AS rules_feedback
        WITH qt, rules_rel + rules_attr + coalesce(rules_feedback, []) AS rules
        
        UNWIND rules AS r
        WITH DISTINCT r
        RETURN
            coalesce(r.id, r.name) AS id,
            coalesce(r.name, '') AS name,
            coalesce(r.text, '') AS text,
            coalesce(r.category, '') AS category,
            coalesce(r.priority, 0) AS priority,
            r.source AS source
        ORDER BY 
            CASE r.priority
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                ELSE 1
            END DESC,
            priority DESC
        """
    
    # Best practice queries
    GET_BEST_PRACTICES = """
        MATCH (qt:QueryType {name: $qt})<-[:APPLIES_TO]-(b:BestPractice)
        RETURN b.id AS id, b.text AS text
        """
    
    # Example queries
    GET_EXAMPLES = """
        MATCH (e:Example)
        RETURN e.id AS id, e.text AS text, e.type AS type
        LIMIT $limit
        """
    
    # Formatting rule queries
    GET_FORMATTING_RULES_FOR_QUERY_TYPE = """
        OPTIONAL MATCH (fr:FormattingRule)
        WHERE (fr.applies_to = 'all' OR fr.applies_to = $query_type)
        WITH fr WHERE fr IS NOT NULL
        RETURN fr.name AS name,
               fr.description AS description,
               fr.priority AS priority,
               fr.category AS category,
               coalesce(fr.examples_good, '') AS examples_good,
               coalesce(fr.examples_bad, '') AS examples_bad
        ORDER BY fr.priority DESC
        """
    
    GET_FORMATTING_RULES = """
        MATCH (t:Template {name: $template_type})-[:ENFORCES]->(r:Rule)
        RETURN r.text AS text, coalesce(r.priority, 999) AS priority
        ORDER BY priority
        """


# Convenience function to get queries
def get_query(name: str) -> str:
    """Get a Cypher query by name.
    
    Args:
        name: Query name (attribute name from CypherQueries class)
        
    Returns:
        Cypher query string
        
    Raises:
        AttributeError: If query name doesn't exist
    """
    return getattr(CypherQueries, name)
