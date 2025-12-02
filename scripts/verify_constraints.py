# mypy: disable-error-code=import-untyped
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tabulate import tabulate
else:
    from tabulate import tabulate  # type: ignore[import-untyped]

# Add project root to path
sys.path.append(os.getcwd())

from neo4j import GraphDatabase

from src.config.settings import AppConfig


def main():
    try:
        config = AppConfig()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    uri = config.neo4j_uri
    user = config.neo4j_user
    password = config.neo4j_password

    if not uri or not user or not password:
        print("Error: Neo4j configuration missing.")
        return

    query = """
    MATCH (qt:QueryType)-[:HAS_CONSTRAINT]->(c:Constraint)
    RETURN qt.name as type, 
           c.name as constraint_name,
           c.priority as priority,
           c.category as category,
           substring(c.description, 0, 80) as description_preview
    ORDER BY qt.name, c.priority DESC
    """

    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            driver.verify_connectivity()
            with driver.session() as session:
                result = session.run(query)
                records = [dict(record) for record in result]

                if not records:
                    with open("verification_result.txt", "w", encoding="utf-8") as f:
                        f.write("No constraints found.")
                    return

                table = tabulate(records, headers="keys", tablefmt="grid")
                with open("verification_result.txt", "w", encoding="utf-8") as f:
                    f.write(table)
                print("Verification result written to verification_result.txt")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
