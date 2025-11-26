"""Basic usage examples for the package."""

from src.config import AppConfig
from src.agent import GeminiAgent  # noqa: F401
from src.infra.utils import clean_markdown_code_block
from src.infra.logging import setup_logging

# Configuration
config = AppConfig(
    model_name="gemini-1.5-flash",
    temperature=0.7,
)

# Agent
# Note: GeminiAgent requires GEMINI_API_KEY environment variable
# agent = GeminiAgent(config=config)
# result = agent.run("Explain quantum computing")
# print(result)

# Q&A System
# from src.qa.rag_system import QAKnowledgeGraph
# qa = QAKnowledgeGraph()
# answer = qa.query("What is machine learning?")
# print(answer)

# Utilities
setup_logging(level="INFO")
cleaned = clean_markdown_code_block("```python\nprint('hello')\n```")
print(f"Cleaned code: {cleaned}")
