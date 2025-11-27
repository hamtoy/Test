import asyncio
import logging
from src.agent.core import GeminiAgent
from src.workflow.hybrid_optimizer import HybridWorkflowOptimizer
from src.config import AppConfig

# 로깅 설정
logging.basicConfig(level=logging.INFO)


async def main():
    # Mock Agent Setup
    try:
        config = AppConfig()
        agent = GeminiAgent(config=config)
    except Exception as e:
        logging.warning(f"GeminiAgent initialization failed: {e}. Using Mock object.")

        # Mock LLMProvider
        class MockLLMProvider:
            async def generate_content_async(self, prompt, **kwargs):
                class Result:
                    content = "mock content"
                    usage = {"total_tokens": 10}

                return Result()

        class MockAgent:
            def __init__(self):
                self.llm_provider = MockLLMProvider()

            async def generate_content_async(self, prompt, **kwargs):
                class Result:
                    content = "mock content"
                    usage = {}

                return Result()

        agent = MockAgent()

    templates = ["ocr_v1.j2", "ocr_v2.j2", "rag_simple.j2"]

    optimizer = HybridWorkflowOptimizer(agent, templates)

    print("=== Test 1: Simple Query (Expected: MCTS) ===")
    simple_query = "Extract the date from this invoice."
    res1 = await optimizer.optimize(simple_query, mode="auto")
    print(f"Result: {res1}\n")

    print("=== Test 2: Complex Query (Expected: LATS) ===")
    complex_query = "Why represents the relationship between these two documents considering the date discrepancy?"
    res2 = await optimizer.optimize(complex_query, mode="auto")
    print(f"Result: {res2}\n")


if __name__ == "__main__":
    asyncio.run(main())
