# -*- coding: utf-8 -*-
"""Main entry point for Gemini Workflow System - Interactive Menu Mode."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import USER_INTERRUPT_MESSAGE
from src.infra.logging import setup_logging
from src.ui import console
from src.ui.interactive_menu import interactive_main


async def main() -> None:
    """Main entry point - launches interactive menu."""
    # Setup logging
    logger, log_listener = setup_logging(log_level=None)

    try:
        # Load configuration
        config = AppConfig()

        # Configure Gemini API
        import google.generativeai as genai

        genai.configure(api_key=config.api_key)  # type: ignore[attr-defined]

        # Setup Jinja2 environment
        from jinja2 import Environment, FileSystemLoader

        if not config.template_dir.exists():
            raise FileNotFoundError(
                f"Templates directory missing: {config.template_dir}"
            )
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir), autoescape=True
        )

        # Create agent
        agent = GeminiAgent(config, jinja_env=jinja_env)

        # Launch interactive menu
        await interactive_main(agent, config, logger)

    except (FileNotFoundError, ValueError, OSError) as e:
        logger.critical("[FATAL] Initialization failed: %s", e)
        console.print(f"[red]초기화 실패: {e}[/red]")
        sys.exit(1)
    finally:
        log_listener.stop()


if __name__ == "__main__":
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
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print(USER_INTERRUPT_MESSAGE)
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 - Top-level handler must catch all exceptions
        logging.critical("Critical error: %s", e, exc_info=True)
        sys.exit(1)
