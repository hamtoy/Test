"""Test DynamicExampleSelector with migrated examples."""

from dotenv import load_dotenv

from src.processing.example_selector import DynamicExampleSelector
from src.qa.rag_system import QAKnowledgeGraph

load_dotenv(override=True)

kg = QAKnowledgeGraph()
selector = DynamicExampleSelector(kg)

print("Testing DynamicExampleSelector...")
examples = selector.select_best_examples("explanation", {}, k=2)

print(f"Found: {len(examples)} examples")
for ex in examples:
    text = ex.get("example", "")[:100]
    print(f"  - {text}...")
