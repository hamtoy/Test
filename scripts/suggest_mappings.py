import json
import re
from difflib import SequenceMatcher


def normalize_text(text):
    """텍스트 정규화 (공백, 특수문자 제거)"""
    if not text:
        return ""
    text = re.sub(r"[❌⭕*\(\)]", "", text)
    text = " ".join(text.split())
    return text.lower().strip()


def find_keywords(text):
    """텍스트에서 주요 키워드 추출"""
    if not text:
        return set()
    stopwords = {
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "의",
        "에",
        "에서",
        "로",
        "으로",
        "와",
        "과",
        "한",
        "하는",
        "입니다",
        "다",
        "합니다",
        "제공된",
        "자료의",
    }
    words = set(re.findall(r"\w+", normalize_text(text)))
    return words - stopwords


def calculate_similarity(text1, text2):
    """두 텍스트 간 유사도 계산"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    seq_sim = SequenceMatcher(None, norm1, norm2).ratio()

    keywords1 = find_keywords(text1)
    keywords2 = find_keywords(text2)
    if keywords1 and keywords2:
        keyword_sim = len(keywords1 & keywords2) / len(keywords1 | keywords2)
    else:
        keyword_sim = 0

    substring_sim = 0
    if norm2 in norm1 or norm1 in norm2:
        substring_sim = 0.5

    return (seq_sim * 0.4) + (keyword_sim * 0.4) + (substring_sim * 0.2)


def suggest_mappings():
    with open("rules_export.json", "r", encoding="utf-8") as f:
        rules = json.load(f)

    with open("examples_export.json", "r", encoding="utf-8") as f:
        examples = json.load(f)

    print(f"📊 Rules: {len(rules)}, Examples: {len(examples)}\n")

    mappings = []

    for example in examples:
        ex_id = example["id"]
        ex_text = example["text"]
        ex_type = example["type"]

        matches = []
        for rule in rules:
            rule_id = rule["id"]
            rule_text = rule["text"]

            similarity = calculate_similarity(ex_text, rule_text)

            if similarity > 0.15:
                matches.append(
                    {
                        "rule_id": rule_id,
                        "rule_text": rule_text,
                        "similarity": similarity,
                    }
                )

        matches.sort(key=lambda x: x["similarity"], reverse=True)

        if matches:
            best_match = matches[0]
            mappings.append(
                {
                    "ex_id": ex_id,
                    "rule_id": best_match["rule_id"],
                    "ex_type": ex_type,
                    "ex_text": ex_text[:80],
                    "rule_text": best_match["rule_text"][:80],
                    "similarity": best_match["similarity"],
                }
            )

    with open("mapping_suggestions.json", "w", encoding="utf-8") as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)

    print(f"✅ Generated {len(mappings)} mapping suggestions\n")

    print("=" * 80)
    print("상위 매핑 제안 (similarity > 0.25):")
    print("=" * 80)

    high_confidence = [m for m in mappings if m["similarity"] > 0.25]
    for i, mapping in enumerate(high_confidence[:15], 1):
        print(f"\n{i}. [{mapping['ex_type']}] Similarity: {mapping['similarity']:.2f}")
        print(f"   Example ID: {mapping['ex_id']}")
        print(f"   Example: {mapping['ex_text']}...")
        print(f"   Rule ID: {mapping['rule_id']}")
        print(f"   Rule: {mapping['rule_text']}...")

    print("\n" + "=" * 80)
    print("graph_schema_builder.py에 추가할 코드:")
    print("=" * 80)
    print("\nmanual_mappings = [")
    for mapping in high_confidence[:15]:
        print(
            f'    {{"ex_id": "{mapping["ex_id"]}", "rule_id": "{mapping["rule_id"]}"}},  # sim: {mapping["similarity"]:.2f}'
        )
    print("]")

    return mappings


if __name__ == "__main__":
    suggest_mappings()
