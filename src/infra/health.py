from __future__ import annotations

import datetime
from typing import Any, Dict, TYPE_CHECKING

import logging

if TYPE_CHECKING:
    from src.qa.rag_system import QAKnowledgeGraph


def check_neo4j_connection(kg: QAKnowledgeGraph | None = None) -> bool:
    """Return True if a simple Neo4j query succeeds."""
    try:
        from neo4j.exceptions import Neo4jError
    except ImportError:
        logging.getLogger(__name__).warning(
            "Cannot check Neo4j connection: neo4j package not available"
        )
        return False

    if kg is None:
        try:
            from src.qa.rag_system import QAKnowledgeGraph

            kg = QAKnowledgeGraph()
        except ImportError:
            logging.getLogger(__name__).warning(
                "Cannot check Neo4j connection: QAKnowledgeGraph not available"
            )
            return False
    graph_obj = getattr(kg, "_graph", None)
    if graph_obj is None:
        return False
    try:
        with graph_obj.session() as session:  # noqa: SLF001
            session.run("RETURN 1").single()
        return True
    except Neo4jError:
        return False
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Neo4j health check failed: %s", exc)
        return False


def health_check() -> Dict[str, Any]:
    """Basic health check report."""
    neo4j_ok = check_neo4j_connection()
    return {
        "status": "healthy" if neo4j_ok else "unhealthy",
        "neo4j": neo4j_ok,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
