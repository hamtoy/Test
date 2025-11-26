from __future__ import annotations

import datetime
from typing import Any, Dict

import logging

from neo4j.exceptions import Neo4jError

from src.qa.rag_system import QAKnowledgeGraph


def check_neo4j_connection(kg: QAKnowledgeGraph | None = None) -> bool:
    """Return True if a simple Neo4j query succeeds."""
    graph = kg or QAKnowledgeGraph()
    graph_obj = getattr(graph, "_graph", None)
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
