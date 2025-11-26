"""Neo4j Example-Rule 매핑 카운트 스크립트."""

import logging

from dotenv import load_dotenv

from src.infra.neo4j import get_neo4j_driver_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def count_mappings() -> int:
    """Example-Rule 매핑 수를 조회."""
    with (
        get_neo4j_driver_from_env() as driver,
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
