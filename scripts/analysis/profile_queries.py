#!/usr/bin/env python3
"""Neo4j Cypher query profiling script.

This script analyzes the execution plans of key Cypher queries
using PROFILE and EXPLAIN to identify optimization opportunities.

Usage:
    uv run python scripts/analysis/profile_queries.py

Environment variables required:
    NEO4J_URI: Neo4j connection URI
    NEO4J_USER: Neo4j username
    NEO4J_PASSWORD: Neo4j password
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class QueryProfile:
    """Profile result for a single query."""

    name: str
    query: str
    db_hits: int
    rows: int
    elapsed_ms: float
    plan_operators: list[str]
    warnings: list[str]


# Key queries to profile
QUERIES_TO_PROFILE = [
    {
        "name": "Rule-Constraint Matching",
        "query": """
            MATCH (r:Rule), (c:Constraint)
            WHERE (r.text CONTAINS c.description) OR (r.text CONTAINS c.id)
            RETURN count(*) AS matches
        """,
    },
    {
        "name": "Example-Rule Relationship",
        "query": """
            MATCH (e:Example {type: 'positive'}), (r:Rule)
            WHERE e.text CONTAINS r.text OR r.text CONTAINS e.text
            RETURN count(*) AS matches
        """,
    },
    {
        "name": "QueryType Keyword Matching",
        "query": """
            MATCH (r:Rule), (q:QueryType)
            WHERE ANY(kw IN ['설명', '해석'] WHERE toLower(r.text) CONTAINS toLower(kw))
            RETURN count(*) AS matches
        """,
    },
    {
        "name": "Template-Constraint Traversal",
        "query": """
            MATCH (t:Template)-[:ENFORCES]->(c:Constraint)
            RETURN t.name, collect(c.id) AS constraints
        """,
    },
    {
        "name": "Graph Summary Statistics",
        "query": """
            MATCH (n)
            RETURN labels(n) AS label, count(*) AS count
            ORDER BY count DESC
        """,
    },
]


def profile_query(
    session: Any,
    name: str,
    query: str,
) -> QueryProfile:
    """Profile a single query and extract execution metrics."""
    profile_query = f"PROFILE {query}"

    try:
        result = session.run(profile_query)
        summary = result.consume()

        # Extract profile from summary
        profile = summary.profile
        if profile is None:
            return QueryProfile(
                name=name,
                query=query,
                db_hits=0,
                rows=0,
                elapsed_ms=0,
                plan_operators=[],
                warnings=["No profile data available"],
            )

        # Calculate total db_hits recursively
        def get_total_db_hits(operator: Any) -> int:
            total = operator.get("dbHits", 0)
            for child in operator.get("children", []):
                total += get_total_db_hits(child)
            return total

        # Get operator types
        def get_operators(operator: Any) -> list[str]:
            ops = [operator.get("operatorType", "Unknown")]
            for child in operator.get("children", []):
                ops.extend(get_operators(child))
            return ops

        db_hits = get_total_db_hits(profile)
        rows = profile.get("rows", 0)
        operators = get_operators(profile)

        # Check for problematic patterns
        warnings: list[str] = []
        if "CartesianProduct" in operators:
            warnings.append(
                "⚠️ CartesianProduct detected - consider restructuring query"
            )
        if "Eager" in operators:
            warnings.append(
                "⚠️ Eager operator - may cause memory issues with large data"
            )
        if "AllNodesScan" in operators:
            warnings.append("⚠️ AllNodesScan - consider adding labels or indexes")

        elapsed_ms = summary.result_available_after or 0

        return QueryProfile(
            name=name,
            query=query,
            db_hits=db_hits,
            rows=rows,
            elapsed_ms=elapsed_ms,
            plan_operators=operators,
            warnings=warnings,
        )

    except Neo4jError as e:
        return QueryProfile(
            name=name,
            query=query,
            db_hits=0,
            rows=0,
            elapsed_ms=0,
            plan_operators=[],
            warnings=[f"Query error: {e}"],
        )


def print_profile_report(profiles: list[QueryProfile]) -> None:
    """Print formatted profile report."""
    print("\n" + "=" * 70)
    print("NEO4J QUERY PROFILE REPORT")
    print("=" * 70)

    for p in profiles:
        print(f"\n📊 {p.name}")
        print("-" * 50)
        print(f"   DB Hits: {p.db_hits:,}")
        print(f"   Rows: {p.rows:,}")
        print(f"   Time: {p.elapsed_ms:.2f}ms")
        print(f"   Operators: {' → '.join(p.plan_operators[:5])}")

        if p.warnings:
            print("   Warnings:")
            for w in p.warnings:
                print(f"      {w}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_db_hits = sum(p.db_hits for p in profiles)
    total_time = sum(p.elapsed_ms for p in profiles)
    warnings_count = sum(len(p.warnings) for p in profiles)

    print(f"   Total DB Hits: {total_db_hits:,}")
    print(f"   Total Time: {total_time:.2f}ms")
    print(f"   Warnings: {warnings_count}")

    if warnings_count == 0:
        print("\n   ✅ All queries look optimized!")
    else:
        print(f"\n   ⚠️ {warnings_count} optimization opportunities found")


def main() -> None:
    """Main entry point."""
    # Check environment variables
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        print("❌ Missing environment variables: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        sys.exit(1)

    driver = GraphDatabase.driver(uri, auth=(user, password))  # type: ignore

    try:
        with driver.session() as session:
            print("🔍 Profiling Neo4j queries...")

            profiles: list[QueryProfile] = []
            for q in QUERIES_TO_PROFILE:
                profile = profile_query(session, q["name"], q["query"])
                profiles.append(profile)

            print_profile_report(profiles)

    except Neo4jError as e:
        print(f"❌ Neo4j connection error: {e}")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
