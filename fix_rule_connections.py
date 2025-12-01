"""모든 Rule과 QueryType을 연결해주는 임시 스크립트."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


def main() -> None:
    load_dotenv()

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    with driver.session() as session:
        result = session.run(
            """
            MATCH (r:Rule), (qt:QueryType)
            WHERE NOT (r)-[:APPLIES_TO]->(qt)
            MERGE (r)-[:APPLIES_TO]->(qt)
            RETURN count(*) AS created
            """
        )
        created = result.single()["created"]
        print(f"새로 연결: {created}개")

    driver.close()
    print("완료!")


if __name__ == "__main__":
    main()
