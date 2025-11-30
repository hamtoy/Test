# 🤖 AI Agent Improvement Prompts

> ## 🚨 MANDATORY: FILE MODIFICATION REQUIRED
> 
> **⛔ DO NOT just respond with text or code blocks.**
> **⛔ DO NOT say "you can modify like this" without actually modifying.**
> **⛔ DO NOT explain what needs to be done without doing it.**
> 
> **✅ YOU MUST use file editing tools (`replace_string_in_file`, `create_file`, `multi_replace_string_in_file`) to directly modify files.**
> **✅ After each prompt, confirm "I have modified the file(s)" with the actual changes made.**
> 
> ---
> 
> **Process ALL prompts below SEQUENTIALLY. Do NOT stop after completing one prompt.**

---

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | RAG System Additional Module Split | P2 | ⬜ Pending |
| 2 | PROMPT-002 | Complete Docstring Standardization | P3 | ⬜ Pending |

**Total: 2 prompts** | **Completed: 0** | **Remaining: 2**

---

## 🟡 Priority 2 (High) - Execute First

### [PROMPT-001] RAG System Additional Module Split

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-002**

**Task**: Further reduce `src/qa/rag_system.py` from 1005 lines to under 500 lines by extracting more functionality to the existing `src/qa/graph/` modules.

**Files to Modify**: 
- Create `src/qa/graph/session_validator.py` - Extract session validation logic
- Create `src/qa/graph/traversal.py` - Extract graph traversal methods
- Update `src/qa/rag_system.py` - Import from new modules and reduce code

#### Instructions:

1. Analyze `src/qa/rag_system.py` to identify extractable methods (session validation, graph traversal)
2. Create `src/qa/graph/session_validator.py` to extract `validate_*` methods
3. Create `src/qa/graph/traversal.py` to extract `get_descendants`, `traverse_*` methods
4. Update imports in `rag_system.py` to use the new modules
5. Ensure all existing tests still pass

#### Implementation Code:

**File: src/qa/graph/session_validator.py**
```python
"""Session validation utilities for QA knowledge graph.

Provides validation logic for QA sessions, turns, and intent verification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from checks.validate_session import validate_turns

logger = logging.getLogger(__name__)


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
        result = validate_turns(turns)
        
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
                if rule and any(word in intent_lower for word in rule.lower().split()[:3]):
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
```

**File: src/qa/graph/traversal.py**
```python
"""Graph traversal utilities for Neo4j knowledge graph.

Provides methods for traversing and querying the knowledge graph
structure, including descendant discovery and relationship walking.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

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
        else:
            rel_filter = ""
        
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
```

**Update src/qa/graph/__init__.py to export new classes:**
```python
"""Graph-based QA components for RAG system.

This package provides modular components for Neo4j-based knowledge graph operations:
- connection: Neo4j connection management
- vector_search: Vector similarity search
- rule_extractor: Rule extraction and QA generation
- query_executor: Query execution utilities
- session_validator: Session validation logic
- traversal: Graph traversal utilities
"""

from src.qa.graph.connection import Neo4jConnectionManager
from src.qa.graph.query_executor import QueryExecutor, run_async_safely
from src.qa.graph.rule_extractor import RuleExtractor
from src.qa.graph.session_validator import SessionValidator, create_session_validator
from src.qa.graph.traversal import GraphTraversal, create_traversal
from src.qa.graph.vector_search import VectorSearchEngine

__all__ = [
    "Neo4jConnectionManager",
    "QueryExecutor",
    "RuleExtractor",
    "SessionValidator",
    "GraphTraversal",
    "VectorSearchEngine",
    "run_async_safely",
    "create_session_validator",
    "create_traversal",
]
```

#### Verification:
- Run: `python -c "from src.qa.graph import SessionValidator, GraphTraversal; print('Import successful')"`
- Run: `wc -l src/qa/rag_system.py` (target: under 500 lines after refactoring)
- Run: `pytest tests/unit/qa/ -v --tb=short` (verify tests still pass)
- Expected: No import errors, line count significantly reduced

**✅ After completing this prompt, proceed to [PROMPT-002]**

---

## 🟢 Priority 3 (Medium) - Execute Last

### [PROMPT-002] Complete Docstring Standardization

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then ALL PROMPTS ARE COMPLETED.**

**Task**: Run the docstring checker and fix identified style inconsistencies across the codebase.

**Files to Modify**: Various files in `src/` based on check_docstrings.py output

#### Instructions:

1. Run `python scripts/check_docstrings.py src/` to identify issues
2. Fix any NumPy or Sphinx style docstrings to Google style
3. Focus on high-priority modules: `src/agent/`, `src/core/`, `src/qa/`
4. Verify ruff D rules are properly configured in pyproject.toml

#### Implementation Code:

**Verify pyproject.toml has docstring linting enabled (already done, verify):**

The `[tool.ruff.lint]` section should have "D" in extend-select:

```toml
[tool.ruff.lint]
extend-select = ["PERF", "FURB", "SIM", "D"]
ignore = [
    "D100",   # Missing docstring in public module
    "D101",   # Missing docstring in public class
    "D102",   # Missing docstring in public method
    "D103",   # Missing docstring in public function
    "D104",   # Missing docstring in public package
    "D105",   # Missing docstring in magic method
    "D107",   # Missing docstring in __init__
    "D200",   # One-line docstring should fit on one line
    "D205",   # 1 blank line required between summary line and description
    "D415",   # First line should end with a period, question mark, or exclamation point
]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

**Example docstring fixes to apply:**

1. **NumPy style to Google style conversion:**

Before (NumPy style):
```python
def example_function(param1, param2):
    """Short description.
    
    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int
        Description of param2.
        
    Returns
    -------
    bool
        Description of return value.
    """
```

After (Google style):
```python
def example_function(param1: str, param2: int) -> bool:
    """Short description.
    
    Args:
        param1: Description of param1.
        param2: Description of param2.
        
    Returns:
        Description of return value.
    """
```

2. **Sphinx style to Google style conversion:**

Before (Sphinx style):
```python
def another_function(name):
    """Short description.
    
    :param name: The name parameter
    :type name: str
    :returns: The result
    :rtype: str
    """
```

After (Google style):
```python
def another_function(name: str) -> str:
    """Short description.
    
    Args:
        name: The name parameter
        
    Returns:
        The result
    """
```

#### Target Files to Check and Fix:

1. `src/agent/core.py` - Main agent class docstrings
2. `src/core/models.py` - Pydantic model docstrings
3. `src/qa/rag_system.py` - RAG system docstrings
4. `src/workflow/executor.py` - Workflow execution docstrings
5. `src/web/routes.py` - API route docstrings

#### Verification:
- Run: `python scripts/check_docstrings.py src/ --missing-only | head -20`
- Run: `ruff check src/ --select D --statistics`
- Expected: Minimal style issues, all critical modules using Google style

**🎉 ALL PROMPTS COMPLETED! Run final verification:**

```bash
# Verify graph module imports
python -c "
from src.qa.graph import (
    QueryExecutor, 
    SessionValidator, 
    GraphTraversal,
    run_async_safely
)
print('All graph module imports: OK')
"

# Check rag_system.py line count
wc -l src/qa/rag_system.py

# Run docstring check
python scripts/check_docstrings.py src/config --missing-only

# Run ruff docstring checks
ruff check src/ --select D --statistics | head -10

echo 'All prompts completed successfully!'
```
