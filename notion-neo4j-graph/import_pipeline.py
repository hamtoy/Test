import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase, Session
from notion_client import Client

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("NotionNeo4jPipeline")

load_dotenv()


class DataValidator:
    """데이터 유효성 검증 헬퍼."""

    @staticmethod
    def validate_block(block: Dict[str, Any]) -> bool:
        """블록 데이터 유효성 검증."""
        if not isinstance(block, dict):
            return False
        return not ("id" not in block or "type" not in block)


class NotionExtractor:
    """Notion 데이터 추출 클래스."""

    def __init__(self, token: str):
        """Notion 클라이언트 초기화."""
        self.client = Client(auth=token)

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """페이지 메타데이터 조회."""
        try:
            return self.client.pages.retrieve(page_id)
        except Exception as e:
            logger.error(f"페이지 조회 실패 ({page_id}): {e}")
            return {}

    def get_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        """블록의 자식 블록들을 재귀적으로 조회 (전체 트리)."""
        blocks = []
        cursor = None

        try:
            while True:
                response = self.client.blocks.children.list(
                    block_id=block_id, start_cursor=cursor
                )
                results = response.get("results", [])

                for block in results:
                    # 자식이 있는 경우 재귀적으로 조회
                    if block.get("has_children"):
                        children = self.get_blocks(block["id"])
                        block["children"] = children
                    blocks.append(block)

                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")

        except Exception as e:
            logger.error(f"블록 조회 실패 ({block_id}): {e}")

        return blocks


class Neo4jAuraImporter:
    """Neo4j Aura 최적화 임포터."""

    # 하이픈 + 대문자 허용 Notion URL 패턴
    NOTION_URL_PATTERN = (
        r"https?://(?:www\.)?notion\.so/[^/\s]+/"
        r"([A-Fa-f0-9]{8}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{4}-?[A-Fa-f0-9]{12})"
    )

    BATCH_SIZE = 100
    REFERENCE_BATCH_SIZE = 500

    def __init__(self, uri: str, auth: tuple):
        """Neo4j 드라이버 초기화 및 연결 확인."""
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.verify_connection()

    def close(self):
        """Neo4j 드라이버 연결 종료."""
        self.driver.close()

    def verify_connection(self):
        """Neo4j 서버 연결 상태 확인."""
        try:
            self.driver.verify_connectivity()
            logger.info("✅ Neo4j 연결 확인됨")
        except Exception as e:
            logger.error(f"❌ Neo4j 연결 실패: {e}")
            raise

    @contextmanager
    def session_context(self):
        """Neo4j 세션 컨텍스트 매니저."""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def clear_database(self):
        """데이터베이스 초기화 (주의: 모든 데이터 삭제)."""
        logger.warning("⚠️ 데이터베이스 초기화 중...")
        with self.session_context() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("✅ 데이터베이스 초기화 완료")

    def create_constraints(self):
        """인덱스 및 제약조건 생성."""
        queries = [
            "CREATE CONSTRAINT page_id IF NOT EXISTS FOR (p:Page) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT block_id IF NOT EXISTS FOR (b:Block) REQUIRE b.id IS UNIQUE",
            "CREATE INDEX block_content IF NOT EXISTS FOR (b:Block) ON (b.content)",
        ]
        with self.session_context() as session:
            for q in queries:
                session.run(q)
        logger.info("✅ 제약조건 및 인덱스 생성 완료")

    def import_page(self, page_data: Dict[str, Any], blocks: List[Dict[str, Any]]):
        """페이지와 블록 전체 임포트."""
        page_id = page_data["id"].replace("-", "")
        title = "Untitled"

        # 제목 추출
        props = page_data.get("properties", {})
        title_prop = props.get("title") or props.get("Name")
        if title_prop and "title" in title_prop:
            title = "".join([t["plain_text"] for t in title_prop["title"]])

        url = page_data.get("url", "")

        logger.info(f"📥 페이지 임포트 시작: {title} ({page_id})")

        with self.session_context() as session:
            # 1. 페이지 노드 생성
            session.run(
                """
                MERGE (p:Page {id: $id})
                SET p.title = $title,
                    p.url = $url,
                    p.updated_at = datetime()
            """,
                id=page_id,
                title=title,
                url=url,
            )

            # 2. 블록 임포트 (반복적 방식)
            self._import_blocks_iterative(session, page_id, blocks)

    def _import_blocks_iterative(
        self, session: Session, page_id: str, blocks: List[Dict]
    ):
        # 원본 순서 유지: order는 입력 순서 기준, 스택 push만 역순
        top_level = [(idx, block) for idx, block in enumerate(blocks)]
        stack = [(block, None, None, 0, idx) for idx, block in reversed(top_level)]
        processed_blocks = []

        while stack:
            block, parent_id, prev_sibling_id, depth, order = stack.pop()

            if not DataValidator.validate_block(block):
                continue

            block_id = block["id"]

            # 텍스트 콘텐츠 추출
            content = ""
            block_type = block["type"]
            if block_type in block and "rich_text" in block[block_type]:
                content = "".join(
                    [t["plain_text"] for t in block[block_type]["rich_text"]]
                )

            processed_blocks.append(
                {
                    "id": block_id,
                    "type": block_type,
                    "content": content,
                    "parent_id": parent_id,
                    "page_id": page_id if parent_id is None else None,
                    "prev_sibling_id": prev_sibling_id,
                    "depth": depth,
                    "order": order,
                }
            )

            if block.get("children"):
                children = block["children"]

                # 유효한 자식만 사용
                valid_children = [
                    (i, child)
                    for i, child in enumerate(children)
                    if isinstance(child, dict) and "id" in child
                ]

                # 이전 형제 매핑 (유효한 자식 기준)
                prev_map = {}
                prev_valid_id = None
                for child_idx, child in valid_children:
                    prev_map[child_idx] = prev_valid_id
                    prev_valid_id = child.get("id")

                # 역순 push로 원래 순서 pop
                for child_idx, child in reversed(valid_children):
                    stack.append(
                        (child, block_id, prev_map.get(child_idx), depth + 1, child_idx)
                    )

            if len(processed_blocks) >= self.BATCH_SIZE:
                self._batch_create_blocks(session, processed_blocks)
                processed_blocks = []

        if processed_blocks:
            self._batch_create_blocks(session, processed_blocks)

    def _batch_create_blocks(self, session: Session, blocks_data: List[Dict]):
        """블록 배치 생성 및 관계 설정."""
        query = """
        UNWIND $blocks AS block_data
        MERGE (b:Block {id: block_data.id})
        SET b.type = block_data.type,
            b.content = block_data.content,
            b.depth = block_data.depth,
            b.order = block_data.order
        
        // 페이지 연결 (최상위 블록인 경우)
        WITH b, block_data
        CALL {
            WITH b, block_data
            WITH b, block_data
            WHERE block_data.page_id IS NOT NULL
            MATCH (p:Page {id: block_data.page_id})
            MERGE (p)-[:HAS_BLOCK]->(b)
        }
        
        // 부모 블록 연결
        CALL {
            WITH b, block_data
            WITH b, block_data
            WHERE block_data.parent_id IS NOT NULL
            MATCH (parent:Block {id: block_data.parent_id})
            MERGE (parent)-[:HAS_CHILD]->(b)
        }
        
        // 이전 형제 연결 (순서 보장용)
        CALL {
            WITH b, block_data
            WITH b, block_data
            WHERE block_data.prev_sibling_id IS NOT NULL
            MATCH (prev:Block {id: block_data.prev_sibling_id})
            MERGE (prev)-[:NEXT]->(b)
        }
        """
        session.run(query, blocks=blocks_data)

    def create_cross_references(self):
        """페이지 간 교차 참조(멘션) 관계 생성."""
        pattern = re.compile(self.NOTION_URL_PATTERN)

        with self.session_context() as session:
            offset = 0
            total_refs = 0

            while True:
                result = session.run(
                    """
                    MATCH (b:Block)
                    WHERE b.content CONTAINS 'notion.so'
                    RETURN b.id AS block_id, b.content AS content
                    ORDER BY b.id
                    SKIP $offset
                    LIMIT $limit
                """,
                    offset=offset,
                    limit=self.REFERENCE_BATCH_SIZE,
                )

                records = list(result)
                if not records:
                    break

                references = []
                for record in records:
                    block_id = record["block_id"]
                    content = record["content"]

                    for page_id_raw in pattern.findall(content):
                        clean_id = page_id_raw.replace("-", "")
                        references.append({"block_id": block_id, "page_id": clean_id})

                if references:
                    session.execute_write(self._create_references_tx, references)
                    total_refs += len(references)

                offset += self.REFERENCE_BATCH_SIZE
                logger.info(f"   참조 처리 중... ({offset}개 블록 완료)")

            logger.info(
                "✅ 교차 참조 %d개 생성 완료" % total_refs
                if total_refs
                else "ℹ️  교차 참조 없음"
            )

    @staticmethod
    def _create_references_tx(tx, references):
        query = """
        UNWIND $refs AS ref
        MATCH (b:Block {id: ref.block_id})
        MATCH (p:Page {id: ref.page_id})
        MERGE (b)-[:MENTIONS]->(p)
        """
        tx.run(query, refs=references)


def main():
    """Notion 데이터 가져오기 및 Neo4j 저장 메인 함수."""
    # 환경 변수 확인
    notion_token = os.environ.get("NOTION_TOKEN")
    page_ids_str = os.environ.get("NOTION_PAGE_IDS")
    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")

    if not all([notion_token, page_ids_str, neo4j_uri, neo4j_password]):
        logger.error("❌ 필수 환경 변수가 누락되었습니다 (.env 확인 필요)")
        return

    page_ids = [pid.strip() for pid in page_ids_str.split(",") if pid.strip()]

    # 초기화
    extractor = NotionExtractor(notion_token)
    importer = Neo4jAuraImporter(neo4j_uri, (neo4j_user, neo4j_password))

    try:
        # 1. DB 초기화 및 스키마 설정
        importer.clear_database()
        importer.create_constraints()

        # 2. 페이지별 데이터 추출 및 임포트
        for page_id in page_ids:
            logger.info(f"🔄 처리 중: {page_id}")

            # Notion 데이터 추출
            page_data = extractor.get_page(page_id)
            if not page_data:
                continue

            blocks = extractor.get_blocks(page_id)
            logger.info(f"   - 블록 {len(blocks)}개 추출 완료")

            # Neo4j 임포트
            importer.import_page(page_data, blocks)
            logger.info("   - Neo4j 저장 완료")

        # 3. 교차 참조 생성
        logger.info("🔗 교차 참조(Mentions) 연결 중...")
        importer.create_cross_references()

        logger.info("🎉 모든 작업이 성공적으로 완료되었습니다!")

    except Exception as e:
        logger.error(f"❌ 작업 중 오류 발생: {e}")
    finally:
        importer.close()


if __name__ == "__main__":
    main()
