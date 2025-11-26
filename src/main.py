# -*- coding: utf-8 -*-
import asyncio
import contextlib
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from src.agent import GeminiAgent
from src.cache_analytics import analyze_cache_stats, print_cache_report
from src.cli import parse_args, resolve_checkpoint_path
from src.config import AppConfig
from src.config.constants import LOG_MESSAGES, USER_INTERRUPT_MESSAGE
from src.processing.loader import load_input_data
from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.infra.logging import log_metrics, setup_logging
from src.ui import console, render_budget_panel, render_cost_panel
from src.infra.utils import write_cache_stats
from src.workflow import execute_workflow


genai = SimpleNamespace(configure=lambda *_args, **_kwargs: None)


async def main():
    """Main workflow orchestrator using CLI module for argument parsing"""
    # Parse arguments using cli.py module
    args = parse_args()

    # ... (logging setup)
    logger, log_listener = setup_logging(log_level=args.log_level)
    start_time = datetime.now(timezone.utc)

    # Integrated pipeline quick path (skip Gemini workflow)
    if args.integrated_pipeline:
        try:
            meta_path = Path(args.pipeline_meta)
            if not meta_path.is_absolute():
                meta_path = Path(__file__).resolve().parents[1] / meta_path
            from src.integrated_qa_pipeline import run_integrated_pipeline

            session = run_integrated_pipeline(meta_path)
            console.print("[bold green]Integrated pipeline completed[/bold green]")
            for i, turn in enumerate(session.get("turns", []), 1):
                console.print(
                    "%s. %s: %s..." % (i, turn.get("type"), turn.get("prompt", "")[:80])
                )
        except (OSError, ValueError, RuntimeError) as e:
            logger.critical("[FATAL] Integrated pipeline failed: %s", e)
            log_listener.stop()
            sys.exit(1)
        log_listener.stop()
        return

    # ... (config & resource loading)
    try:
        config = AppConfig()
        import google.generativeai as genai

        genai.configure(api_key=config.api_key)
        # ... (jinja env setup)
        from jinja2 import Environment, FileSystemLoader

        if not config.template_dir.exists():
            raise FileNotFoundError(
                "Templates directory missing: %s" % config.template_dir
            )
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir), autoescape=True
        )

        logger.info("리소스 로드 중...")
        input_dir = config.input_dir
        ocr_text, _ = await load_input_data(input_dir, args.ocr_file, args.cand_file)

    except (FileNotFoundError, ValueError, OSError) as e:
        # ... (error handling)
        logger.critical("[FATAL] Initialization failed: %s", e)
        log_listener.stop()
        sys.exit(1)

    # Agent에 모든 의존성 주입 (Dependency Injection)
    agent = GeminiAgent(config, jinja_env=jinja_env)
    user_intent = args.intent

    logger.info("워크플로우 시작 (Mode: %s)", args.mode)

    try:
        # Cache analytics quick path
        if args.analyze_cache:
            summary = analyze_cache_stats(config.cache_stats_path)
            print_cache_report(summary)
            log_listener.stop()
            return

        # 워크플로우 실행 (모드에 따라 interactive 설정)
        # CHAT 모드이거나 --interactive 플래그가 있으면 대화형 모드
        is_interactive = (args.mode == "CHAT") or args.interactive
        checkpoint_path = resolve_checkpoint_path(
            config.output_dir, args.checkpoint_file
        )

        await execute_workflow(
            agent,
            ocr_text,
            user_intent,
            logger,
            args.ocr_file,
            args.cand_file,
            config,
            is_interactive,
            resume=args.resume,
            checkpoint_path=checkpoint_path,
            keep_progress=args.keep_progress,
        )

        # ... (rest of main)

        # 비용 정보를 Panel로 표시
        console.print()
        if not args.no_budget_panel:
            console.print(render_budget_panel(agent))
        if not args.no_cost_panel:
            console.print(render_cost_panel(agent))

        # Cache stats persistence: append JSONL entry with small retention window
        try:
            cache_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": config.model_name,
                "input_tokens": agent.total_input_tokens,
                "output_tokens": agent.total_output_tokens,
                "cache_hits": agent.cache_hits,
                "cache_misses": agent.cache_misses,
            }
            write_cache_stats(
                config.cache_stats_path, config.cache_stats_max_entries, cache_entry
            )
            logger.info("Cache stats saved to %s", config.cache_stats_path)
        except (OSError, ValueError, TypeError, RuntimeError) as e:
            if hasattr(logger, "warning"):
                logger.warning("Cache stats write skipped: %s", e)
                logger.warning("cache_stats_write_failed")
            else:
                print("Cache stats write skipped: %s" % e)

    except (
        APIRateLimitError,
        ValidationFailedError,
        SafetyFilterError,
        BudgetExceededError,
    ) as e:
        logger.exception(LOG_MESSAGES["workflow_failed"].format(error=e))
    except Exception as e:  # noqa: BLE001 - Top-level handler for unexpected errors
        logger.exception(LOG_MESSAGES["workflow_failed"].format(error=e))
    finally:
        # 로그 리스너 종료 (남은 로그 플러시)
        with contextlib.suppress(Exception):
            elapsed_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            log_metrics(
                logger,
                latency_ms=elapsed_ms,
                prompt_tokens=getattr(agent, "total_input_tokens", 0),
                completion_tokens=getattr(agent, "total_output_tokens", 0),
                cache_hits=getattr(agent, "cache_hits", 0),
                cache_misses=getattr(agent, "cache_misses", 0),
            )
        log_listener.stop()


if __name__ == "__main__":
    load_dotenv()
    if os.name == "nt":
        try:
            policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
            if policy:
                asyncio.set_event_loop_policy(policy())
        except AttributeError:
            pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # from rich.console import Console # Already imported at the top
        console.print(USER_INTERRUPT_MESSAGE)
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 - Top-level handler must catch all exceptions
        logging.critical("Critical error: %s", e, exc_info=True)
        sys.exit(1)
