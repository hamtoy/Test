# src/cli.py
"""Command-line interface argument parsing and optimization utilities."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import List, Optional

import neo4j

from src.infra.neo4j_optimizer import TwoTierIndexManager


@dataclass
class CLIArgs:
    """Command-line arguments container."""

    mode: str = "AUTO"
    interactive: bool = False
    ocr_file: str = "input_ocr.txt"
    cand_file: str = "input_candidates.json"
    intent: Optional[str] = None
    checkpoint_file: str = "checkpoint.jsonl"
    keep_progress: bool = False
    no_cost_panel: bool = False
    no_budget_panel: bool = False
    resume: bool = False
    log_level: str = "INFO"
    analyze_cache: bool = False
    integrated_pipeline: bool = False
    pipeline_meta: str = "examples/session_input.json"
    optimize_neo4j: bool = False
    drop_existing_indexes: bool = False


def parse_args(args: Optional[List[str]] = None) -> CLIArgs:
    """Parse command-line arguments.

    Args:
        args: List of arguments to parse. If None, uses sys.argv.

    Returns:
        CLIArgs: Parsed arguments container.
    """
    parser = argparse.ArgumentParser(
        description="Gemini Workflow System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="AUTO",
        choices=["AUTO", "MANUAL", "BATCH"],
        help="Workflow mode (default: AUTO)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive mode",
    )
    parser.add_argument(
        "--ocr-file",
        type=str,
        default="input_ocr.txt",
        help="OCR input file name",
    )
    parser.add_argument(
        "--cand-file",
        type=str,
        default="input_candidates.json",
        help="Candidate answers file name",
    )
    parser.add_argument(
        "--intent",
        type=str,
        default=None,
        help="User intent for query generation",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default="checkpoint.jsonl",
        help="Checkpoint file path",
    )
    parser.add_argument(
        "--keep-progress",
        action="store_true",
        help="Keep progress between runs",
    )
    parser.add_argument(
        "--no-cost-panel",
        action="store_true",
        help="Disable cost panel display",
    )
    parser.add_argument(
        "--no-budget-panel",
        action="store_true",
        help="Disable budget panel display",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--analyze-cache",
        action="store_true",
        help="Analyze cache statistics",
    )
    parser.add_argument(
        "--integrated-pipeline",
        action="store_true",
        help="Run integrated pipeline",
    )
    parser.add_argument(
        "--pipeline-meta",
        type=str,
        default="examples/session_input.json",
        help="Pipeline metadata file path",
    )
    parser.add_argument(
        "--optimize-neo4j",
        action="store_true",
        help="Run Neo4j index optimization",
    )
    parser.add_argument(
        "--drop-existing-indexes",
        action="store_true",
        help="Drop existing indexes before optimization",
    )

    parsed = parser.parse_args(args)

    return CLIArgs(
        mode=parsed.mode,
        interactive=parsed.interactive,
        ocr_file=parsed.ocr_file,
        cand_file=parsed.cand_file,
        intent=parsed.intent,
        checkpoint_file=parsed.checkpoint_file,
        keep_progress=parsed.keep_progress,
        no_cost_panel=parsed.no_cost_panel,
        no_budget_panel=parsed.no_budget_panel,
        resume=parsed.resume,
        log_level=parsed.log_level,
        analyze_cache=parsed.analyze_cache,
        integrated_pipeline=parsed.integrated_pipeline,
        pipeline_meta=parsed.pipeline_meta,
        optimize_neo4j=parsed.optimize_neo4j,
        drop_existing_indexes=parsed.drop_existing_indexes,
    )


async def run_neo4j_optimization(drop_existing: bool = False) -> None:
    """Run Neo4j 2-Tier index optimization.

    Args:
        drop_existing: If True, drops existing indexes before creating new ones.

    Raises:
        EnvironmentError: If required NEO4J environment variables are not set.
    """
    # Check required environment variables
    required_vars = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
    for var in required_vars:
        if not os.getenv(var):
            raise EnvironmentError(
                f"{var} environment variable is required for Neo4j optimization"
            )

    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    driver = neo4j.AsyncGraphDatabase.driver(
        neo4j_uri, auth=(neo4j_user, neo4j_password)  # type: ignore[arg-type]
    )

    try:
        manager = TwoTierIndexManager(driver)

        if drop_existing:
            await manager.drop_all_indexes()

        await manager.create_all_indexes()
        await manager.list_all_indexes()
    finally:
        await driver.close()
