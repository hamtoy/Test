import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def export_for_mapping():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # Export Rules
        print("📋 Exporting Rules...")
        rules_result = session.run("""
            MATCH (r:Rule)
            RETURN r.id AS id, r.text AS text, r.section AS section
            ORDER BY r.section, r.text
        """)

        rules = [
            {
                "id": record["id"],
                "text": record["text"],
                "section": record["section"],
            }
            for record in rules_result
        ]

        # Export Examples
        print("📝 Exporting Examples...")
        examples_result = session.run("""
            MATCH (e:Example)
            RETURN e.id AS id, e.text AS text, e.type AS type
            ORDER BY e.type, e.text
        """)

        examples = [
            {"id": record["id"], "text": record["text"], "type": record["type"]}
            for record in examples_result
        ]

    driver.close()

    # Save to JSON files
    with open("rules_export.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    with open("examples_export.json", "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)

    print(f"✅ Exported {len(rules)} Rules to rules_export.json")
    print(f"✅ Exported {len(examples)} Examples to examples_export.json")

    # Print sample mappings guide
    print("\n" + "=" * 60)
    print("매핑 가이드:")
    print("=" * 60)
    print("\n예시 (negative):")
    for ex in [e for e in examples if e["type"] == "negative"][:3]:
        print(f"\nID: {ex['id']}")
        print(f"Text: {ex['text'][:80]}...")

    print("\n예시 (positive):")
    for ex in [e for e in examples if e["type"] == "positive"][:3]:
        print(f"\nID: {ex['id']}")
        print(f"Text: {ex['text'][:80]}...")

    print("\n규칙 샘플:")
    for rule in rules[:5]:
        print(f"\nID: {rule['id']}")
        print(f"Section: {rule['section']}")
        print(f"Text: {rule['text'][:80]}...")


if __name__ == "__main__":
    export_for_mapping()
