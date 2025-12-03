"""
Neo4j Aura CSV Import Script
CSV 파일을 읽어서 Neo4j Aura 데이터베이스에 임포트합니다.
"""

import csv
import os
from pathlib import Path

from neo4j import GraphDatabase


class AuraImporter:
    """Neo4j Aura CSV 임포터"""

    def __init__(self, uri: str, username: str, password: str):
        """
        Args:
            uri: Neo4j Aura URI (예: neo4j+s://xxxxx.databases.neo4j.io)
            username: 데이터베이스 사용자명 (기본: neo4j)
            password: 데이터베이스 비밀번호
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        """드라이버 연결 종료"""
        self.driver.close()

    def create_constraints(self):
        """유니크 제약조건 생성"""
        print("Creating constraints...")

        constraints = [
            # Guide Data Constraints
            "CREATE CONSTRAINT unique_category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT unique_subcategory_path IF NOT EXISTS FOR (s:Subcategory) REQUIRE (s.categoryName, s.name) IS UNIQUE",
            "CREATE CONSTRAINT unique_item_path IF NOT EXISTS FOR (i:Item) REQUIRE (i.categoryName, i.subcategoryName, i.name) IS UNIQUE",
            # QnA Data Constraints
            "CREATE CONSTRAINT unique_qa_category_name IF NOT EXISTS FOR (c:QACategory) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT unique_qa_subcategory_path IF NOT EXISTS FOR (s:QASubcategory) REQUIRE (s.categoryName, s.name) IS UNIQUE",
            "CREATE CONSTRAINT unique_qa_topic_path IF NOT EXISTS FOR (t:QATopic) REQUIRE (t.categoryName, t.subcategoryName, t.name) IS UNIQUE",
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(
                        f"  ✓ {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}"
                    )
                except Exception as e:
                    print(f"  ⚠ Constraint already exists or error: {e}")

    def create_indexes(self):
        """인덱스 생성"""
        print("\nCreating indexes...")

        indexes = [
            "CREATE INDEX category_name_idx IF NOT EXISTS FOR (c:Category) ON (c.name)",
            "CREATE INDEX subcategory_name_idx IF NOT EXISTS FOR (s:Subcategory) ON (s.name)",
            "CREATE INDEX item_name_idx IF NOT EXISTS FOR (i:Item) ON (i.name)",
            "CREATE INDEX qa_category_name_idx IF NOT EXISTS FOR (c:QACategory) ON (c.name)",
            "CREATE INDEX qa_subcategory_name_idx IF NOT EXISTS FOR (s:QASubcategory) ON (s.name)",
            "CREATE INDEX qa_topic_name_idx IF NOT EXISTS FOR (t:QATopic) ON (t.name)",
        ]

        with self.driver.session() as session:
            for index in indexes:
                try:
                    session.run(index)
                    print(f"  ✓ {index.split('FOR')[1].strip()}")
                except Exception as e:
                    print(f"  ⚠ Index already exists or error: {e}")

    def import_guide_csv(self, csv_path: str, batch_size: int = 100):
        """
        guide.csv 파일 임포트

        Args:
            csv_path: CSV 파일 경로
            batch_size: 배치 처리 크기
        """
        print(f"\nImporting guide.csv from {csv_path}...")

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        print(f"Total rows: {total}")

        query = """
        UNWIND $batch AS row
        WITH row
        WHERE row.대분류 IS NOT NULL AND trim(row.대분류) <> ''

        MERGE (cat:Category {name: trim(row.대분류)})

        WITH cat, row
        WHERE row.중분류 IS NOT NULL AND trim(row.중분류) <> ''
        MERGE (sub:Subcategory {
            categoryName: cat.name,
            name: trim(row.중분류)
        })
        MERGE (cat)-[:HAS_SUBCATEGORY]->(sub)

        WITH cat, sub, row
        WHERE row.소분류 IS NOT NULL AND trim(row.소분류) <> ''
        MERGE (item:Item {
            categoryName: cat.name,
            subcategoryName: sub.name,
            name: trim(row.소분류)
        })
        SET item.content = row.내용
        MERGE (sub)-[:HAS_ITEM]->(item)
        """

        with self.driver.session() as session:
            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                session.run(query, batch=batch)
                print(f"  Processed {min(i + batch_size, total)}/{total} rows")

        print("✓ Guide data import completed!")

    def import_qna_csv(self, csv_path: str, batch_size: int = 100):
        """
        qna.csv 파일 임포트

        Args:
            csv_path: CSV 파일 경로
            batch_size: 배치 처리 크기
        """
        print(f"\nImporting qna.csv from {csv_path}...")

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        print(f"Total rows: {total}")

        query = """
        UNWIND $batch AS row
        WITH row
        WHERE row.대분류 IS NOT NULL AND trim(row.대분류) <> ''

        MERGE (cat:QACategory {name: trim(row.대분류)})

        WITH cat, row
        WHERE row.중분류 IS NOT NULL AND trim(row.중분류) <> ''
        MERGE (sub:QASubcategory {
            categoryName: cat.name,
            name: trim(row.중분류)
        })
        MERGE (cat)-[:HAS_SUBCATEGORY]->(sub)

        WITH cat, sub, row
        WHERE row.소분류 IS NOT NULL AND trim(row.소분류) <> ''
        MERGE (topic:QATopic {
            categoryName: cat.name,
            subcategoryName: sub.name,
            name: trim(row.소분류)
        })
        SET topic.content = row.내용
        MERGE (sub)-[:HAS_TOPIC]->(topic)
        """

        with self.driver.session() as session:
            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                session.run(query, batch=batch)
                print(f"  Processed {min(i + batch_size, total)}/{total} rows")

        print("✓ QnA data import completed!")

    def create_related_links(self):
        """관련 주제 자동 연결"""
        print("\nCreating related topic links...")

        query = """
        MATCH (t1:QATopic), (t2:QATopic)
        WHERE id(t1) < id(t2)
          AND t1.name = t2.name
          AND t1.subcategoryName <> t2.subcategoryName
        MERGE (t1)-[:RELATED_TO]-(t2)
        RETURN count(*) as links_created
        """

        with self.driver.session() as session:
            result = session.run(query)
            count = result.single()["links_created"]
            print(f"  ✓ Created {count} related topic links")

    def verify_import(self):
        """임포트 결과 확인"""
        print("\n" + "=" * 50)
        print("Import Verification")
        print("=" * 50)

        queries = {
            "Categories": "MATCH (n:Category) RETURN count(n) as count",
            "Subcategories": "MATCH (n:Subcategory) RETURN count(n) as count",
            "Items": "MATCH (n:Item) RETURN count(n) as count",
            "QA Categories": "MATCH (n:QACategory) RETURN count(n) as count",
            "QA Subcategories": "MATCH (n:QASubcategory) RETURN count(n) as count",
            "QA Topics": "MATCH (n:QATopic) RETURN count(n) as count",
            "HAS_SUBCATEGORY": "MATCH ()-[r:HAS_SUBCATEGORY]->() RETURN count(r) as count",
            "HAS_ITEM": "MATCH ()-[r:HAS_ITEM]->() RETURN count(r) as count",
            "HAS_TOPIC": "MATCH ()-[r:HAS_TOPIC]->() RETURN count(r) as count",
            "RELATED_TO": "MATCH ()-[r:RELATED_TO]-() RETURN count(r) as count",
        }

        with self.driver.session() as session:
            for label, query in queries.items():
                result = session.run(query)
                count = result.single()["count"]
                print(f"  {label:20} : {count:5} nodes/relationships")


def main():
    """메인 함수"""
    # Neo4j Aura 연결 정보 (환경변수 또는 직접 입력)
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://your-instance.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-password")

    # CSV 파일 경로
    DESKTOP_PATH = Path.home() / "Desktop"
    GUIDE_CSV = DESKTOP_PATH / "guide.csv"
    QNA_CSV = DESKTOP_PATH / "qna.csv"

    # 연결 정보 확인
    if "your-instance" in NEO4J_URI or "your-password" in NEO4J_PASSWORD:
        print("⚠️  Neo4j Aura 연결 정보를 설정해주세요!")
        print("\n환경변수 설정 방법:")
        print("  export NEO4J_URI='neo4j+s://xxxxx.databases.neo4j.io'")
        print("  export NEO4J_USERNAME='neo4j'")
        print("  export NEO4J_PASSWORD='your-password'")
        print("\n또는 스크립트 내 NEO4J_URI, NEO4J_PASSWORD 값을 직접 수정하세요.")
        return

    # CSV 파일 존재 확인
    if not GUIDE_CSV.exists():
        print(f"⚠️  파일을 찾을 수 없습니다: {GUIDE_CSV}")
        return

    if not QNA_CSV.exists():
        print(f"⚠️  파일을 찾을 수 없습니다: {QNA_CSV}")
        return

    print("=" * 50)
    print("Neo4j Aura CSV Importer")
    print("=" * 50)
    print(f"URI: {NEO4J_URI}")
    print(f"Username: {NEO4J_USERNAME}")
    print(f"Guide CSV: {GUIDE_CSV}")
    print(f"QnA CSV: {QNA_CSV}")
    print("=" * 50)

    # 임포트 실행
    importer = AuraImporter(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    try:
        # 1. 제약조건 및 인덱스 생성
        importer.create_constraints()
        importer.create_indexes()

        # 2. CSV 데이터 임포트
        importer.import_guide_csv(str(GUIDE_CSV))
        importer.import_qna_csv(str(QNA_CSV))

        # 3. 관련 주제 연결
        importer.create_related_links()

        # 4. 결과 확인
        importer.verify_import()

        print("\n✅ Import completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        raise

    finally:
        importer.close()


if __name__ == "__main__":
    main()
