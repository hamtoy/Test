#!/usr/bin/env python3
# scripts/run_ab_test.py
# ruff: noqa: E402
"""
Example script for running A/B tests on prompt variants.

Usage:
    python scripts/run_ab_test.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.core import GeminiAgent
from src.config import AppConfig
from src.qa.ab_test import ExperimentConfig, PromptExperimentManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Test dataset (OCR text examples)
TEST_DATA = [
    {
        "id": "doc_1",
        "input_text": "Invoice #12345 Amount: $500 Date: 2025-01-01",
        "user_intent": "Extract invoice details",
    },
    {
        "id": "doc_2",
        "input_text": "Receipt for services rendered... Total: 30,000 KRW",
        "user_intent": "Summarize receipt",
    },
    {
        "id": "doc_3",
        "input_text": "Contract Agreement between Party A and Party B",
        "user_intent": "Review contract terms",
    },
    {
        "id": "doc_4",
        "input_text": "Meeting notes: Q4 review, budget allocation",
        "user_intent": "Extract action items",
    },
    {
        "id": "doc_5",
        "input_text": "Product Manual v2.0 - Installation Guide",
        "user_intent": "Find installation steps",
    },
]


async def main() -> None:
    """Run the A/B test experiment."""
    try:
        config = AppConfig()
    except Exception as e:
        logger.error("Failed to load configuration: %s", e)
        logger.info("Make sure GEMINI_API_KEY is set in your environment")
        return

    agent = GeminiAgent(config)
    manager = PromptExperimentManager(agent)

    exp_config = ExperimentConfig(
        name="ocr_prompt_optimization_v1",
        control_prompt_template="user/query_gen.j2",  # Default (verbose)
        treatment_prompt_template="experiments/ocr_v2_concise.j2",  # Concise variant
        sample_size=5,
        output_dir="experiments/results",
    )

    logger.info("Starting A/B test experiment...")
    report = await manager.run_experiment(exp_config, TEST_DATA)

    print("\n" + "=" * 50)
    print("=== Experiment Report ===")
    print("=" * 50)
    print(f"Experiment: {report['experiment']}")
    print(f"Timestamp: {report['timestamp']}")
    print()
    print("Control Group:")
    print(f"  - Average Latency: {report['control']['avg_latency']:.2f}s")
    print(f"  - Average Cost: ${report['control']['avg_cost']:.6f}")
    print(f"  - Success Rate: {report['control']['success_rate']:.1%}")
    print()
    print("Treatment Group:")
    print(f"  - Average Latency: {report['treatment']['avg_latency']:.2f}s")
    print(f"  - Average Cost: ${report['treatment']['avg_cost']:.6f}")
    print(f"  - Success Rate: {report['treatment']['success_rate']:.1%}")
    print()
    print(f"Winner: {report['winner']}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
