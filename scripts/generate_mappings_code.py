import json

# Load mapping suggestions
with open("mapping_suggestions.json", "r", encoding="utf-8") as f:
    mappings = json.load(f)

# Filter high confidence
high_conf = [m for m in mappings if m["similarity"] > 0.25]

print(f"Found {len(high_conf)} high-confidence mappings (> 0.25)")

# Generate manual_mappings list
manual_mappings_code = "manual_mappings = [\n"
for m in high_conf:
    manual_mappings_code += f'    {{"ex_id": "{m["ex_id"]}", "rule_id": "{m["rule_id"]}"}},  # sim: {m["similarity"]:.2f}\n'
manual_mappings_code += "]\n"

print("\n생성된 manual_mappings 코드:")
print("=" * 60)
print(manual_mappings_code)

# Save to file for easy copy-paste
with open("manual_mappings_code.txt", "w", encoding="utf-8") as f:
    f.write(manual_mappings_code)

print("=" * 60)
print(f"✅ Saved to manual_mappings_code.txt")
print(f"✅ {len(high_conf)} mappings ready to add to graph_schema_builder.py")
