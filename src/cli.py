# -*- coding: utf-8 -*-
"""CLI argument parsing module for Gemini Workflow.

This module contains argument parsing logic extracted from main.py
following the Single Responsibility Principle (SRP).
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CLIArgs:
    """Data class for CLI arguments."""

    mode: str
    interactive: bool
    ocr_file: str
    cand_file: str
    intent: Optional[str]
    checkpoint_file: str
    keep_progress: bool
    no_cost_panel: bool
    no_budget_panel: bool
    resume: bool
    log_level: Optional[str]
    analyze_cache: bool
    integrated_pipeline: bool
    pipeline_meta: str
    optimize_neo4j: bool
    drop_existing_indexes: bool


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="🚀 Advanced Gemini Workflow: AI-powered Q&A Evaluation System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core Configuration
    core_group = parser.add_argument_group("Core Configuration")
    core_group.add_argument(
        "--mode",
        type=str,
        choices=["AUTO", "CHAT"],
        default="AUTO",
        help="Execution mode",
    )
    core_group.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive mode (ask for confirmation) even in AUTO mode",
    )
    core_group.add_argument(
        "--intent",
        type=str,
        default=None,
        help="Optional user intent to guide query generation",
    )
    core_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume workflow using checkpoint file (skips completed queries)",
    )
    core_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override log level (otherwise from LOG_LEVEL env)",
    )
    core_group.add_argument(
        "--analyze-cache",
        action="store_true",
        help="Print cache stats summary and exit",
    )
    core_group.add_argument(
        "--integrated-pipeline",
        action="store_true",
        help="Run integrated QA pipeline (graph + validation) instead of the standard workflow",
    )
    core_group.add_argument(
        "--pipeline-meta",
        type=str,
        default="examples/session_input.json",
        help="Path to JSON metadata file for integrated pipeline mode",
    )
    core_group.add_argument(
        "--optimize-neo4j",
        action="store_true",
        help="Optimize Neo4j database with 2-Tier indexing and exit",
    )
    core_group.add_argument(
        "--drop-existing-indexes",
        action="store_true",
        help="Drop existing indexes before creating new ones (use with --optimize-neo4j)",
    )

    # Input/Output
    io_group = parser.add_argument_group("Input/Output")
    io_group.add_argument(
        "--ocr-file",
        type=str,
        default="input_ocr.txt",
        help="OCR input filename (relative to data/inputs by default)",
    )
    io_group.add_argument(
        "--cand-file",
        type=str,
        default="input_candidates.json",
        help="Candidate answers filename (relative to data/inputs by default)",
    )
    io_group.add_argument(
        "--checkpoint-file",
        type=str,
        default="checkpoint.jsonl",
        help="Checkpoint JSONL path (relative paths resolve under data/outputs)",
    )

    # Debugging
    debug_group = parser.add_argument_group("Debugging")
    debug_group.add_argument(
        "--keep-progress",
        action="store_true",
        help="Keep progress bar visible after completion (for debugging)",
    )
    debug_group.add_argument(
        "--no-cost-panel",
        action="store_true",
        help="Skip cost panel summary output",
    )
    debug_group.add_argument(
        "--no-budget-panel",
        action="store_true",
        help="Skip budget panel summary output",
    )

    return parser


def parse_args(argv: Optional[list[str]] = None) -> CLIArgs:
    """Parse command line arguments.

    Args:
        argv: Optional list of arguments. If None, uses sys.argv.

    Returns:
        CLIArgs dataclass with parsed arguments
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    return CLIArgs(
        mode=args.mode,
        interactive=args.interactive,
        ocr_file=args.ocr_file,
        cand_file=args.cand_file,
        intent=args.intent,
        checkpoint_file=args.checkpoint_file,
        keep_progress=args.keep_progress,
        no_cost_panel=args.no_cost_panel,
        no_budget_panel=args.no_budget_panel,
        resume=args.resume,
        log_level=args.log_level,
        analyze_cache=args.analyze_cache,
        integrated_pipeline=args.integrated_pipeline,
        pipeline_meta=args.pipeline_meta,
        optimize_neo4j=args.optimize_neo4j,
        drop_existing_indexes=args.drop_existing_indexes,
    )


def resolve_checkpoint_path(output_dir: Path, checkpoint_file: str) -> Path:
    """Resolve checkpoint path relative to output directory.

    Args:
        output_dir: Output directory path
        checkpoint_file: Checkpoint file path (may be relative)

    Returns:
        Absolute path to checkpoint file
    """
    checkpoint_path = Path(checkpoint_file)
    if not checkpoint_path.is_absolute():
        checkpoint_path = output_dir / checkpoint_path
    return checkpoint_path


async def run_neo4j_optimization(drop_existing: bool = False) -> None:
    """Run Neo4j 2-Tier index optimization.

    Args:
        drop_existing: If True, drop existing indexes before creating new ones.

    Raises:
        EnvironmentError: If Neo4j environment variables are not set.
        Exception: If index creation fails.
    """
    import os

    from neo4j import AsyncGraphDatabase

    from src.infra.neo4j_optimizer import TwoTierIndexManager

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        raise EnvironmentError(
            "Missing required Neo4j environment variables: "
            "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
        )

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        manager = TwoTierIndexManager(driver)

        if drop_existing:
            print("⚠️  Dropping existing indexes...")
            await manager.drop_all_indexes()

        print("🔧 Creating 2-Tier index architecture...")
        await manager.create_all_indexes()

        indexes = await manager.list_all_indexes()
        print(f"✅ Created {len(indexes)} indexes")

        for idx in indexes:
            print(f"  - {idx.get('name', 'unknown')}: {idx.get('type', 'unknown')}")

    finally:
        await driver.close()
