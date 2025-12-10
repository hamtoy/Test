# mypy: disable-error-code=import-untyped
import os
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tabulate import tabulate
else:
    try:
        from tabulate import tabulate  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - optional dependency for local scripts
        pytest.skip(
            "tabulate not installed; skipping constraint script tests",
            allow_module_level=True,
        )

# Add project root to path
sys.path.append(os.getcwd())

from src.qa.rag_system import QAKnowledgeGraph


def main():
    print("Initializing QAKnowledgeGraph...")
    try:
        kg = QAKnowledgeGraph()
    except Exception as e:
        print(f"Failed to initialize QAKnowledgeGraph: {e}")
        return

    query_types = ["target_short", "target_long", "explanation", "reasoning"]

    for qt in query_types:
        print(f"\nTesting get_constraints_for_query_type('{qt}')...")
        try:
            constraints = kg.get_constraints_for_query_type(qt)
            if not constraints:
                print(f"No constraints found for {qt}.")
            else:
                print(tabulate(constraints, headers="keys", tablefmt="grid"))
        except Exception as e:
            print(f"Error retrieving constraints for {qt}: {e}")

    kg.close()


if __name__ == "__main__":
    main()
