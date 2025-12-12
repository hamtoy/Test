"""추론답변예시.txt를 Neo4j Example 노드로 등록하는 스크립트."""

import hashlib
import re
from pathlib import Path

from dotenv import load_dotenv

from src.infra.neo4j import get_neo4j_driver_from_env

load_dotenv()


def import_reasoning_examples():
    """추론답변예시.txt 파일을 Neo4j에 등록."""
    examples_file = Path("data/examples/추론답변예시.txt")

    if not examples_file.exists():
        print(f"❌ 파일 없음: {examples_file}")
        return

    # 파일 읽기
    content = examples_file.read_text(encoding="utf-8")

    # 멀티라인 답변 지원: 각 엔트리는 "로 끝나고, 다음 줄은 새 질문으로 시작
    entries = re.split(r'"\r?\n(?=[^\r\n])', content)

    qa_pairs = []
    for i, entry in enumerate(entries):
        entry = entry.strip()
        if not entry:
            continue

        # 마지막 엔트리가 아니면 닫는 따옴표 추가
        if i < len(entries) - 1:
            entry = entry + '"'

        # 탭 구분자 찾기
        tab_pos = entry.find("\t")
        if tab_pos == -1:
            continue

        question = entry[:tab_pos].strip()
        answer = entry[tab_pos + 1 :].strip()

        # 따옴표 제거
        answer = answer.removeprefix('"').removesuffix('"')
        # 줄바꿈 정규화
        answer = answer.replace("\r\n", "\n").replace("\r", "\n")

        if question and answer:
            qa_pairs.append({"question": question, "answer": answer})

    print(f"📝 {len(qa_pairs)}개 QA 쌍 추출")

    # Neo4j에 저장
    safe_driver = get_neo4j_driver_from_env()
    driver = safe_driver.driver

    saved_count = 0
    with driver.session() as session:
        for qa in qa_pairs:
            # 해시 기반 ID
            qa_text = f"{qa['question']}|{qa['answer']}"
            example_id = (
                f"reasoning_{hashlib.sha256(qa_text.encode()).hexdigest()[:16]}"
            )

            # Example 노드 생성
            session.run(
                """
                MERGE (e:Example {id: $id})
                SET e.question = $question,
                    e.answer = $answer,
                    e.query_type = 'reasoning',
                    e.status = 'approved',
                    e.type = 'positive',
                    e.success_rate = 1.0,
                    e.usage_count = 0,
                    e.created_at = datetime(),
                    e.source = 'manual_import'
            """,
                id=example_id,
                question=qa["question"],
                answer=qa["answer"],
            )

            # QueryType 노드와 연결
            session.run(
                """
                MATCH (e:Example {id: $example_id})
                MERGE (qt:QueryType {name: 'reasoning'})
                MERGE (e)-[:FOR_TYPE]->(qt)
            """,
                example_id=example_id,
            )

            saved_count += 1

    print(f"✅ {saved_count}개 reasoning Example 저장 완료!")

    safe_driver.close()


if __name__ == "__main__":
    import_reasoning_examples()
