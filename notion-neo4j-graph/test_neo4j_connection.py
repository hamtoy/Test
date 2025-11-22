import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def test_neo4j_connection():
    """Neo4j Aura 연결 테스트"""

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    print(f"🔌 Neo4j Aura 연결 시도...")
    print(f"   URI: {uri}")
    print(f"   User: {user}")

    try:
        # 드라이버 생성
        driver = GraphDatabase.driver(uri, auth=(user, password))

        # 연결 확인
        with driver.session() as session:
            result = session.run("RETURN 'Connection successful!' AS message")
            record = result.single()
            print(f"\n✅ {record['message']}")

            # 데이터베이스 정보
            result = session.run("""
                CALL dbms.components() 
                YIELD name, versions, edition 
                RETURN name, versions[0] AS version, edition
            """)
            for record in result:
                print(f"\n📊 Neo4j 정보:")
                print(f"   Edition: {record['edition']}")
                print(f"   Version: {record['version']}")

        driver.close()
        return True

    except Exception as e:
        print(f"\n❌ 연결 실패: {e}")
        print("\n해결 방법:")
        print("1. NEO4J_URI가 정확한지 확인 (neo4j+s://로 시작)")
        print("2. 비밀번호가 올바른지 확인")
        print("3. Aura 인스턴스가 실행 중인지 확인")
        print("4. 방화벽이 포트 7687을 차단하지 않는지 확인")
        return False


if __name__ == "__main__":
    test_neo4j_connection()
