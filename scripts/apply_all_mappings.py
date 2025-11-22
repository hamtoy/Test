import json
import re

# Load all mapping suggestions
with open("mapping_suggestions.json", "r", encoding="utf-8") as f:
    mappings = json.load(f)

# Sort by similarity (highest first)
mappings_sorted = sorted(mappings, key=lambda x: x["similarity"], reverse=True)

print(f"전체 매핑 제안: {len(mappings_sorted)}개")
print("모든 매핑을 추가합니다...\n")

# Read current graph_schema_builder.py
with open("graph_schema_builder.py", "r", encoding="utf-8") as f:
    content = f.read()

# Generate new manual_mappings list with ALL mappings
mappings_code = "            # 수동 매핑 테이블 (텍스트 유사도 기반 - 전체 27개 매핑)\n"
mappings_code += "            manual_mappings = [\n"
for m in mappings_sorted:
    mappings_code += f'                {{"ex_id": "{m["ex_id"]}", "rule_id": "{m["rule_id"]}"}},  # sim: {m["similarity"]:.3f}\n'
mappings_code += "            ]"

# Find and replace the manual_mappings section
pattern = r"(            # 수동 매핑 테이블.*?\n            manual_mappings = \[.*?\n            \])"
match = re.search(pattern, content, re.DOTALL)

if match:
    new_content = content[: match.start()] + mappings_code + content[match.end() :]

    # Write back
    with open("graph_schema_builder.py", "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ graph_schema_builder.py 업데이트 완료!")
    print(f"✅ {len(mappings_sorted)}개 manual_mappings 추가됨\n")

    # Show statistics
    print("=" * 60)
    print("매핑 통계:")
    print("=" * 60)
    high = len([m for m in mappings_sorted if m["similarity"] >= 0.5])
    med = len([m for m in mappings_sorted if 0.3 <= m["similarity"] < 0.5])
    low = len([m for m in mappings_sorted if m["similarity"] < 0.3])

    print(f"고신뢰도 (>= 0.5): {high}개")
    print(f"중간신뢰도 (0.3-0.5): {med}개")
    print(f"저신뢰도 (< 0.3): {low}개")

    # Show top 5 and bottom 5
    print("\n" + "=" * 60)
    print("상위 5개 매핑:")
    print("=" * 60)
    for i, m in enumerate(mappings_sorted[:5], 1):
        print(f"{i}. Sim: {m['similarity']:.3f}")
        print(f"   Ex: {m['ex_text'][:60]}...")
        print(f"   Rule: {m['rule_text'][:60]}...")

    print("\n" + "=" * 60)
    print("하위 5개 매핑:")
    print("=" * 60)
    for i, m in enumerate(mappings_sorted[-5:], len(mappings_sorted) - 4):
        print(f"{i}. Sim: {m['similarity']:.3f}")
        print(f"   Ex: {m['ex_text'][:60]}...")
        print(f"   Rule: {m['rule_text'][:60]}...")
else:
    print("❌ manual_mappings 섹션을 찾을 수 없습니다")
