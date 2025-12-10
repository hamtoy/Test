"""마크다운/포맷팅 관련 Rule 분석 스크립트."""

import os
import sys

from neo4j import GraphDatabase


def analyze_markdown_rules():
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 Neo4j 연결: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session() as session:
            print("=" * 70)
            print("🔍 마크다운/포맷팅 관련 Rule 검색")
            print("=" * 70)

            query = """
                MATCH (r:Rule)
                WHERE 
                    r.text CONTAINS '마크다운' OR 
                    r.text CONTAINS '볼드' OR 
                    r.text CONTAINS '형식' OR 
                    r.text CONTAINS '강조' OR
                    r.text CONTAINS 'Markdown' OR
                    r.text CONTAINS 'bold'
                RETURN r.id, r.text, r.priority, r.query_type
                ORDER BY r.priority DESC
            """

            result = session.run(query)
            rules = list(result)

            print(f"발견된 Rule: {len(rules)}개\n")

            for i, rec in enumerate(rules, 1):
                text = rec["r.text"]
                print(f"[{i}] ID: {rec['r.id']}")
                print(f"    Priority: {rec['r.priority']}")
                print(f"    Query Type: {rec['r.query_type']}")
                print(f"    Text: {text}")
                print("-" * 70)

    finally:
        driver.close()


if __name__ == "__main__":
    analyze_markdown_rules()
