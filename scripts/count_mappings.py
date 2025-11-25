"""Neo4j Example-Rule 매핑 카운트 스크립트."""

import logging
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_required_env(var: str) -> str:
    """환경변수를 가져오고, 없으면 예외 발생."""
    value = os.getenv(var)
    if value is None:
        raise EnvironmentError(f"Required env var missing: {var}")
    return value


def count_mappings() -> int:
    """Example-Rule 매핑 수를 조회."""
    uri = get_required_env("NEO4J_URI")
    user = get_required_env("NEO4J_USER")
    pwd = get_required_env("NEO4J_PASSWORD")

    with (
        GraphDatabase.driver(uri, auth=(user, pwd)) as driver,
        driver.session() as session,
    ):
        result = session.run("""
            MATCH (e:Example)-[:DEMONSTRATES]->(r:Rule)
            RETURN count(e) AS mapping_count
        """)
        record = result.single()
        if record is None:
            raise RuntimeError("Query returned no results")
        return record["mapping_count"]


if __name__ == "__main__":
    count = count_mappings()
    logger.info("✅ 현재 매핑 수: %s", count)
