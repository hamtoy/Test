"""모든 Rule과 QueryType을 연결해주는 임시 스크립트."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase


def main() -> None:
    load_dotenv()

    uri: Optional[str] = os.getenv("NEO4J_URI")
    user: Optional[str] = os.getenv("NEO4J_USER")
    password: Optional[str] = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        raise ValueError("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD 환경 변수가 필요합니다.")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        result = session.run(
            """
            MATCH (r:Rule), (qt:QueryType)
            WHERE NOT (r)-[:APPLIES_TO]->(qt)
            MERGE (r)-[:APPLIES_TO]->(qt)
            RETURN count(*) AS created
            """
        )
        record = result.single()
        created = int(record["created"]) if record and "created" in record else 0
        print(f"새로 연결: {created}개")

    driver.close()
    print("완료!")


if __name__ == "__main__":
    main()
