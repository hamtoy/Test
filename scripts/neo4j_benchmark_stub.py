"""
Lightweight Neo4j/RAG latency probe.

Usage (optional):
    python scripts/neo4j_benchmark_stub.py

Environment:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD must be set if you want to hit a real DB.

If env vars are missing, the script prints a notice and exits without error.
"""

from __future__ import annotations

import os
import time
from typing import Any, List

from src.qa_rag_system import QAKnowledgeGraph


def _maybe_env(name: str) -> str | None:
    return os.getenv(name)


def _format_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def run_probe() -> None:
    if not all(_maybe_env(k) for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")):
        print("Neo4j credentials missing; skipping probe.")
        return

    kg = QAKnowledgeGraph()
    print("Running Neo4j probe...")

    samples: List[tuple[str, Any]] = [
        ("constraints", lambda: kg.get_constraints_for_query_type("explanation")),
        ("best_practices", lambda: kg.get_best_practices("explanation")),
        ("examples", lambda: kg.get_examples(limit=3)),
    ]

    for name, fn in samples:
        start = time.perf_counter()
        try:
            result = fn()
            dur = _format_ms(start)
            print(f"{name}: {dur} ms, rows={len(result)}")
        except Exception as exc:  # noqa: BLE001
            dur = _format_ms(start)
            print(f"{name}: failed in {dur} ms -> {exc}")

    kg.close()


if __name__ == "__main__":
    run_probe()
