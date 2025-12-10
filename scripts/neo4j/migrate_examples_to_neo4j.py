#!/usr/bin/env python3
"""설명답변예시.txt를 Neo4j Example 노드로 마이그레이션.

Usage:
    uv run python scripts/migrate_examples_to_neo4j.py
"""

import hashlib
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file (override system env vars)
import re

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)


def load_examples(filepath: str = "설명답변예시.txt") -> list[dict]:
    """설명답변예시.txt에서 예시 로드 (멀티라인 형식 지원)."""
    examples = []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by pattern: question ends with tab, answer is in quotes
    # Format: 질문\t"답변 (여러 줄)..."

    # Pattern: 질문으로 시작하고 탭 + "로 시작하는 답변
    # 다음 질문이 나오기 전까지가 하나의 예시

    # Split content by entries (each entry ends with ")
    entries = re.split(r'"\r?\n(?=[^\r\n])', content)

    for i, entry in enumerate(entries):
        entry = entry.strip()
        if not entry:
            continue

        # Add back the closing quote if not the last entry
        if i < len(entries) - 1:
            entry = entry + '"'

        # Find tab separator
        tab_pos = entry.find("\t")
        if tab_pos == -1:
            continue

        question = entry[:tab_pos].strip()
        answer = entry[tab_pos + 1 :].strip()

        # Remove surrounding quotes
        answer = answer.removeprefix('"')
        answer = answer.removesuffix('"')

        # Clean up answer (remove \r characters)
        answer = answer.replace("\r\n", "\n").replace("\r", "\n")

        # Only include sufficiently long examples (800+ chars)
        if len(answer) >= 800:
            example_id = hashlib.sha256(
                f"{question}:{answer[:100]}".encode()
            ).hexdigest()[:16]

            examples.append(
                {
                    "id": f"fewshot_{example_id}",
                    "question": question,
                    "answer": answer,
                    "answer_length": len(answer),
                    "type": "fewshot",  # Distinguish from pattern examples
                    "query_type": "explanation",
                    "success_rate": 1.0,  # Known good examples
                }
            )

    return examples


def migrate_to_neo4j(examples: list[dict]) -> int:
    """Neo4j에 Example 노드 생성."""
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_uri:
        print("❌ NEO4J_URI not set")
        return 0

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    created_count = 0

    try:
        with driver.session() as session:
            # Ensure QueryType node exists
            session.run("""
                MERGE (qt:QueryType {name: 'explanation'})
                SET qt.description = '전체 설명형 답변'
            """)

            for ex in examples:
                # Upsert Example node
                result = session.run(
                    """
                    MERGE (e:Example {id: $id})
                    SET e.question = $question,
                        e.text = $answer,
                        e.answer_length = $answer_length,
                        e.type = $type,
                        e.query_type = $query_type,
                        e.success_rate = $success_rate,
                        e.context_has_table = false,
                        e.usage_count = 0,
                        e.migrated_at = datetime()
                    WITH e
                    MATCH (qt:QueryType {name: $query_type})
                    MERGE (e)-[:FOR_TYPE]->(qt)
                    RETURN e.id AS id
                """,
                    **ex,
                )

                record = result.single()
                if record:
                    created_count += 1
                    print(f"  ✅ {ex['id'][:20]}... ({ex['answer_length']} chars)")

    finally:
        driver.close()

    return created_count


def main():
    print("=" * 60)
    print("📚 Few-Shot Examples Migration to Neo4j")
    print("=" * 60)

    # Load examples
    print("\n1️⃣ Loading examples from 설명답변예시.txt...")
    examples = load_examples()
    print(f"   Found {len(examples)} examples with 800+ chars")

    if not examples:
        print("❌ No examples found!")
        return

    # Show stats
    lengths = [ex["answer_length"] for ex in examples]
    print(f"   Min length: {min(lengths)} chars")
    print(f"   Max length: {max(lengths)} chars")
    print(f"   Avg length: {sum(lengths) // len(lengths)} chars")

    # Migrate
    print("\n2️⃣ Migrating to Neo4j...")
    created = migrate_to_neo4j(examples)

    print("\n" + "=" * 60)
    print(f"✅ Migration complete! Created/updated {created} Example nodes")
    print("=" * 60)


if __name__ == "__main__":
    main()
