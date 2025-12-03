"""Initialize Neo4j schema for QA formatting rules."""

from __future__ import annotations

import os
from typing import Iterable

from neo4j import GraphDatabase


def _get_env_or_raise(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _run_statements(
    uri: str, user: str, password: str, statements: Iterable[str]
) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for stmt in statements:
                session.run(stmt)
    finally:
        driver.close()


def init_formatting_rule_schema() -> None:
    """Create constraint and default FormattingRule node if missing."""
    statements = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (fr:FormattingRule) REQUIRE fr.name IS UNIQUE;",
        """
        MERGE (fr:FormattingRule {name: 'default'})
        SET fr.applies_to = 'all',
            fr.description = 'Default formatting rule',
            fr.priority = 0,
            fr.category = 'general',
            fr.examples_good = '',
            fr.examples_bad = '';
        """,
    ]

    uri = _get_env_or_raise("NEO4J_URI")
    user = _get_env_or_raise("NEO4J_USER")
    password = _get_env_or_raise("NEO4J_PASSWORD")

    _run_statements(uri, user, password, statements)


if __name__ == "__main__":
    init_formatting_rule_schema()
