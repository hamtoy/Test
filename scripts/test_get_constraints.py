import os
import sys

from tabulate import tabulate

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
