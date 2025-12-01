"""Session validation utilities for QA knowledge graph.

Provides validation logic for QA sessions, turns, and intent verification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Number of leading words from a rule to check for intent alignment
MAX_RULE_WORDS_TO_CHECK = 3


def validate_turns_basic(turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Basic validation for turn structure.
    
    Args:
        turns: List of turn dictionaries
        
    Returns:
        Validation result with status and errors
    """
    errors = []
    for i, turn in enumerate(turns):
        if "query" not in turn:
            errors.append(f"Turn {i}: missing 'query' field")
        if "response" not in turn:
            errors.append(f"Turn {i}: missing 'response' field")
    
    return {"valid": len(errors) == 0, "errors": errors}


class SessionValidator:
    """Validates QA session structures and data integrity.
    
    Provides methods to validate session metadata, turn sequences,
    and intent alignment with the knowledge graph.
    
    Args:
        query_executor: QueryExecutor instance for graph queries
    """
    
    def __init__(self, query_executor: Any) -> None:
        """Initialize the session validator."""
        self._executor = query_executor
    
    def validate_session_structure(
        self,
        session_id: str,
        turns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate the structure of a QA session.
        
        Args:
            session_id: Unique identifier for the session
            turns: List of turn dictionaries with query/response pairs
            
        Returns:
            Validation result with status and any error messages
        """
        result = validate_turns_basic(turns)
        
        return {
            "session_id": session_id,
            "valid": result.get("valid", False),
            "turn_count": len(turns),
            "errors": result.get("errors", []),
        }
    
    def validate_intent_alignment(
        self,
        intent: str,
        query_type: str,
    ) -> bool:
        """Check if intent aligns with QueryType rules.
        
        Args:
            intent: The user's stated intent
            query_type: The classified query type
            
        Returns:
            True if intent aligns with query type rules
        """
        cypher = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (qt)<-[:APPLIES_TO]-(r:Rule)
        RETURN qt.name AS query_type, collect(r.text) AS rules
        """
        
        try:
            results = self._executor.execute(cypher, {"qt": query_type})
            if not results:
                return True  # No rules defined, allow
            
            rules = results[0].get("rules", [])
            # Basic alignment check - intent should relate to at least one rule
            intent_lower = intent.lower()
            for rule in rules:
                if rule and any(
                    word in intent_lower
                    for word in rule.lower().split()[:MAX_RULE_WORDS_TO_CHECK]
                ):
                    return True
            
            return len(rules) == 0  # No rules means no constraints
        except Exception as e:
            logger.warning("Intent alignment check failed: %s", e)
            return True  # Fail open for validation


def create_session_validator(query_executor: Any) -> SessionValidator:
    """Factory function to create a SessionValidator.
    
    Args:
        query_executor: QueryExecutor instance for graph queries
        
    Returns:
        Configured SessionValidator instance
    """
    return SessionValidator(query_executor)
