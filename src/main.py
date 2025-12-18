# mypy: disable-error-code=attr-defined
"""Main entry point for Gemini Workflow System - Interactive Menu Mode."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.config import AppConfig
from src.config.constants import USER_INTERRUPT_MESSAGE
from src.infra.logging import setup_logging
from src.llm.init_genai import configure_genai as _configure_genai
from src.ui import console


class _GenAIProxy:
    def configure(self, *, api_key: str) -> None:
        _configure_genai(api_key=api_key)


genai = _GenAIProxy()

__all__ = [
    "USER_INTERRUPT_MESSAGE",
    "analyze_cache_stats",
    "console",
    "execute_workflow",
    "format_output",
    "genai",
    "get_gemini_agent",
    "GeminiAgent",  # Backward compatibility alias
    "interactive_main",
    "load_dotenv",
    "load_input_data",
    "main",
    "parse_args",
    "print_cache_report",
    "render_cost_panel",
    "write_cache_stats",
]


def get_gemini_agent(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import GeminiAgent."""
    from src.agent import GeminiAgent as _GeminiAgent

    return _GeminiAgent(*args, **kwargs)


# Backward compatibility alias - keep for existing code that uses GeminiAgent directly
GeminiAgent = get_gemini_agent


async def interactive_main(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import interactive_main."""
    from src.ui.interactive_menu import interactive_main as _interactive_main

    return await _interactive_main(*args, **kwargs)


def analyze_cache_stats(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import analyze_cache_stats."""
    from src.caching.analytics import analyze_cache_stats as _analyze_cache_stats

    return _analyze_cache_stats(*args, **kwargs)


def print_cache_report(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import print_cache_report."""
    from src.caching.analytics import print_cache_report as _print_cache_report

    return _print_cache_report(*args, **kwargs)


def parse_args(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import parse_args."""
    from src.cli import parse_args as _parse_args

    return _parse_args(*args, **kwargs)


def format_output(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import format_output."""
    from src.cli import format_output as _format_output

    return _format_output(*args, **kwargs)


def write_cache_stats(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import write_cache_stats."""
    from src.infra.utils import write_cache_stats as _write_cache_stats

    return _write_cache_stats(*args, **kwargs)


async def load_input_data(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import load_input_data."""
    from src.processing.loader import load_input_data as _load_input_data

    return await _load_input_data(*args, **kwargs)


def render_cost_panel(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import render_cost_panel."""
    from src.ui.panels import render_cost_panel as _render_cost_panel

    return _render_cost_panel(*args, **kwargs)


async def execute_workflow(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
    """Lazily import execute_workflow."""
    from src.workflow import execute_workflow as _execute_workflow

    return await _execute_workflow(*args, **kwargs)


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _maybe_get_mock_llm_provider() -> Any | None:
    if not (_is_truthy_env("SQ_MOCK_LLM") or _is_truthy_env("SQ_E2E")):
        return None
    from src.llm.mock_provider import MockLLMProvider

    return MockLLMProvider()


async def _run_non_interactive(args: Any) -> int:
    logger, log_listener = setup_logging(log_level=args.log_level)

    try:
        config = AppConfig()
        genai.configure(api_key=config.api_key)

        from jinja2 import Environment, FileSystemLoader

        if not config.template_dir.exists():
            raise FileNotFoundError(
                f"Templates directory missing: {config.template_dir}",
            )
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir),
            autoescape=True,
        )

        llm_provider = _maybe_get_mock_llm_provider()
        agent = get_gemini_agent(config, jinja_env=jinja_env, llm_provider=llm_provider)

        ocr_text, _ = await load_input_data(
            base_dir=config.input_dir,
            ocr_filename=args.ocr_file,
            cand_filename=args.cand_file,
        )

        results = await execute_workflow(
            agent=agent,
            ocr_text=ocr_text,
            user_intent=args.intent,
            logger=logger,
            ocr_filename=args.ocr_file,
            cand_filename=args.cand_file,
            config=config,
            is_interactive=False,
            resume=args.resume,
            checkpoint_path=Path(args.checkpoint_file),
            keep_progress=args.keep_progress,
        )

        if not results:
            logger.error("Non-interactive workflow produced no results")
            return 1

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, object] = {
                "status": "ok",
                "turns": [r.model_dump() for r in results],
            }
            output_path.write_text(
                format_output(payload, args.output_format),
                encoding="utf-8",
            )

        return 0
    except (OSError, ValueError) as e:
        logger.critical("[FATAL] Non-interactive run failed: %s", e)
        console.print(f"[red]실행 실패: {e}[/red]")
        return 1
    finally:
        log_listener.stop()


async def main() -> None:
    """Main entry point - launches interactive menu."""
    # Setup logging
    logger, log_listener = setup_logging(log_level=None)

    try:
        # Load configuration
        config = AppConfig()
        genai.configure(api_key=config.api_key)

        # Setup Jinja2 environment
        from jinja2 import Environment, FileSystemLoader

        if not config.template_dir.exists():
            raise FileNotFoundError(
                f"Templates directory missing: {config.template_dir}",
            )
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir),
            autoescape=True,
        )

        # Create agent
        agent = get_gemini_agent(config, jinja_env=jinja_env)

        # Launch interactive menu
        await interactive_main(agent, config, logger)

    except (OSError, ValueError) as e:
        logger.critical("[FATAL] Initialization failed: %s", e)
        console.print(f"[red]초기화 실패: {e}[/red]")
        sys.exit(1)
    finally:
        log_listener.stop()


if __name__ == "__main__":
    args: Any | None = None
    args = parse_args()

    if args.config is not None:
        if not Path(args.config).exists():
            console.print(f"[red]설정 파일이 없습니다: {args.config}[/red]")
            sys.exit(2)
        load_dotenv(dotenv_path=args.config)
    else:
        load_dotenv()

    # Windows event loop policy
    if os.name == "nt":
        try:
            policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
            if policy:
                asyncio.set_event_loop_policy(policy())
        except AttributeError:
            pass

    try:
        if args.non_interactive:
            sys.exit(asyncio.run(_run_non_interactive(args)))
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print(USER_INTERRUPT_MESSAGE)
        sys.exit(130)
    except Exception as e:
        logging.critical("Critical error: %s", e, exc_info=True)
        sys.exit(1)
