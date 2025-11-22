import json

with open("mapping_suggestions.json", "r", encoding="utf-8") as f:
    mappings = json.load(f)

print(f"총 {len(mappings)}개 매핑 제안\n")

# Filter high confidence
high_conf = [m for m in mappings if m["similarity"] > 0.25]

print(f"고신뢰도 매핑 (similarity > 0.25): {len(high_conf)}개\n")
print("=" * 80)

for i, m in enumerate(high_conf[:15], 1):
    print(f"\n{i}. [{m['ex_type']}] Similarity: {m['similarity']:.3f}")
    print(f"   Ex: {m['ex_text']}")
    print(f"   Rule: {m['rule_text']}")

print("\n" + "=" * 80)
print("graph_schema_builder.py에 추가할 manual_mappings:")
print("=" * 80)
print()
for m in high_conf[:15]:
    print(
        f'    {{"ex_id": "{m["ex_id"]}", "rule_id": "{m["rule_id"]}"}},  # {m["similarity"]:.2f}'
    )
