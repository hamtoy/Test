# -*- coding: utf-8 -*-
import os
import sys
import logging
import asyncio
import argparse
import json
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

# pip install python-dotenv google-generativeai aiofiles pydantic tenacity pydantic-settings jinja2 rich
from dotenv import load_dotenv
from pydantic import ValidationError
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm

from src.config import AppConfig
from src.agent import GeminiAgent
from src.models import WorkflowResult
from src.data_loader import load_input_data
from src.logging_setup import setup_logging
from src.utils import safe_json_parse
from src.exceptions import ValidationFailedError, CacheCreationError

# [Global Console] Rich Console은 전역에서 재사용
console = Console()

def save_result_to_file(result: WorkflowResult, config: AppConfig):
    """[Config Injection] 결과를 Markdown 파일로 저장 (하드코딩 제거)"""
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"result_turn_{result.turn_id}_{timestamp}.md"
    
    content = f"""# Turn {result.turn_id} Result

## Query
{result.query}

## Evaluation
- **Best Candidate**: {result.evaluation.best_candidate}
- **Scores**:
{chr(10).join([f"  - {e.candidate_id}: {e.score} ({e.reason})" for e in result.evaluation.evaluations])}

## Best Answer ({result.evaluation.best_candidate})
{result.best_answer}

## Rewritten Answer
{result.rewritten_answer}

## Metadata
- **Cost**: ${result.cost:.4f}
- **Timestamp**: {timestamp}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    logging.getLogger("GeminiWorkflow").info(f"결과 파일 저장됨: {filename}")


async def _evaluate_and_rewrite_turn(
    agent: GeminiAgent,
    ocr_text: str,
    query: str,
    candidates: Dict[str, str],
    cache,
    turn_id: int,
    total_turns: int,
    logger: logging.Logger,
) -> Optional[WorkflowResult]:
    logger.info(f"Turn {turn_id}/{total_turns}: '{query}' 실행 중...")

    logger.info("후보 평가 중...")
    evaluation = await agent.evaluate_responses(ocr_text, query, candidates, cached_content=cache)
    if not evaluation:
        logger.warning(f"Turn {turn_id}: 평가 실패")
        return None

    best_candidate_id = evaluation.get_best_candidate_id()
    logger.info(f"후보 선정 완료: {best_candidate_id}")

    raw_answer = candidates.get(best_candidate_id, "")
    parsed = safe_json_parse(raw_answer, best_candidate_id)
    best_answer = parsed if parsed else raw_answer

    logger.info("답변 재작성 중...")
    rewritten_answer = await agent.rewrite_best_answer(ocr_text, best_answer, cached_content=None)
    logger.info("답변 재작성 완료")

    return WorkflowResult(
        turn_id=turn_id,
        query=query,
        evaluation=evaluation,
        best_answer=best_answer,
        rewritten_answer=rewritten_answer,
        cost=agent.get_total_cost(),
        success=True,
    )


async def execute_workflow(agent: GeminiAgent, ocr_text: str, user_intent: Optional[str], logger: logging.Logger, ocr_filename: str, cand_filename: str, is_interactive: bool = True) -> List[WorkflowResult]:
    """
    [Orchestration] 전체 워크플로우 실행 (Iterative & Human-in-the-Loop)
    1. Planning: 질의 리스트 생성
    2. Breakpoint: 사용자 검토 및 데이터 Hot Reload (is_interactive=True일 때만)
    3. Execution Loop: 각 질의에 대해 평가 및 재작성 수행
    
    Args:
        is_interactive: True면 사용자에게 확인 요청, False면 자동 진행 (AUTO 모드)
    """
    # [Phase 1: Planning] 질의 리스트 생성
    logger.info("질의 리스트 생성 중...")
    queries = await agent.generate_query(ocr_text, user_intent)
    
    if not queries:
        logger.error("질의 생성 실패")
        return []

    # [Rich UI] 생성된 질의 리스트 출력
    console.print(Panel(
        "\n".join([f"{i+1}. {q}" for i, q in enumerate(queries)]),
        title="[bold green]Generated Strategic Queries[/bold green]",
        border_style="green"
    ))

    # [Conditional Interactivity] AUTO 모드에서는 프롬프트 건너뛰기
    config = AppConfig()
    candidates = {}  # Initialize candidates
    
    if is_interactive:
        # [Breakpoint & Hot Reload] 사용자 개입
        if Confirm.ask("위 질의를 보고 후보 답변 파일(input_candidates.json)을 수정하시겠습니까? (수정 후 Enter)", default=True):
            logger.info("사용자 요청으로 데이터 재로딩 중...")
            try:
                _, candidates = await load_input_data(config.input_dir, ocr_filename, cand_filename)
                logger.info("데이터 재로딩 완료")
            except Exception as e:
                logger.error(f"데이터 재로딩 실패: {e}")
                return []
        else:
            # 재로딩 없이 진행
            _, candidates = await load_input_data(config.input_dir, ocr_filename, cand_filename)
    else:
        # [AUTO Mode] 자동으로 데이터 로드 (프롬프트 없음)
        logger.info("AUTO 모드: 데이터 자동 로딩 중...")
        _, candidates = await load_input_data(config.input_dir, ocr_filename, cand_filename)

    # [Context Caching] 캐시 생성 시도
    logger.info("Context Caching 시도 중...")
    try:
        cache = await agent.create_context_cache(ocr_text)
    except CacheCreationError as e:
        cache = None
        logger.warning(f"Context cache creation skipped: {e}")

    results = []
    
    # [Phase 2: Execution Loop] 순차 실행
    for i, query in enumerate(queries):
        turn_id = i + 1
        try:
            result = await _evaluate_and_rewrite_turn(
                agent=agent,
                ocr_text=ocr_text,
                query=query,
                candidates=candidates,
                cache=cache,
                turn_id=turn_id,
                total_turns=len(queries),
                logger=logger,
            )
            if not result:
                continue
            
            results.append(result)
            
            # 결과 저장 (Config injection)
            save_result_to_file(result, config)
            
            # [Rich UI] 턴 결과 출력
            console.print(Panel(
                f"[bold]Query:[/bold] {query}\\n\\n"
                f"[bold]Best Candidate:[/bold] {result.evaluation.get_best_candidate_id()}\\n"
                f"[bold]Rewritten:[/bold] {result.rewritten_answer[:200]}...",
                title=f"Turn {turn_id} Result",
                border_style="blue"
            ))

            
        except Exception as e:
            logger.exception(f"Turn {turn_id} 실행 중 오류 발생: {e}")
            
    # [Cleanup] 캐시 삭제
    if cache:
        try:
            cache.delete()
            logger.info(f"Cache cleaned up: {cache.name}")
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

    return results

async def main():
    """Main workflow orchestrator with professional argument parsing"""
    parser = argparse.ArgumentParser(
        description="🚀 Advanced Gemini Workflow: AI-powered Q&A Evaluation System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter  # Auto-show defaults
    )

    # 1. Core Configuration
    core_group = parser.add_argument_group("Core Configuration")
    core_group.add_argument(
        "--mode",
        type=str,
        choices=["AUTO", "CHAT"],
        default="AUTO",
        help="Execution mode"
    )

    # 2. Input Sources
    input_group = parser.add_argument_group("Input Sources")
    input_group.add_argument(
        "--ocr-file",
        type=str,
        default="input_ocr.txt",
        metavar="FILE",
        help="OCR text input file"
    )
    input_group.add_argument(
        "--cand-file",
        type=str,
        default="input_candidates.json",
        metavar="FILE",
        help="Candidate answers file (JSON)"
    )

    # 3. Chat Mode Options
    chat_group = parser.add_argument_group("Chat Mode Options")
    chat_group.add_argument(
        "--intent",
        type=str,
        default="Summarize the key points",
        help="User intent for CHAT mode"
    )

    args = parser.parse_args()

    # [Separation of Concerns] 로깅 설정을 별도 모듈로 분리
    # from src.logging_setup import setup_logging # Already imported at the top
    # [Logging] Non-Blocking 로깅 초기화 (logger, listener 반환)
    logger, log_listener = setup_logging()
    
    # [Configuration] Pydantic Settings로 환경변수와 기본값 통합 관리
    try:
        config = AppConfig()
        genai.configure(api_key=config.api_key)
    except ValidationError as e:
        logger.critical(f"설정 오류: {e}")
        log_listener.stop()
        sys.exit(1)

    # [DI Preparation] Resources Initialization
    try:
        # 1. Jinja 환경을 Main에서 생성 (IoC 원칙)
        from jinja2 import Environment, FileSystemLoader
        
        if not config.template_dir.exists():
            raise FileNotFoundError(f"Templates directory missing: {config.template_dir}")
        
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir),
            autoescape=True
        )
        
        # 2. 데이터 로드 (초기 로드)
        logger.info("리소스 로드 중...")
        input_dir = config.input_dir
        ocr_text, _ = await load_input_data(input_dir, args.ocr_file, args.cand_file)
        
    except (FileNotFoundError, ValueError, json.JSONDecodeError, ValidationFailedError) as e:
        logger.critical(f"초기화 실패: {e}")
        log_listener.stop()
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Unexpected error during initialization: {e}")
        log_listener.stop()
        sys.exit(1)

    # [DI] Agent에 모든 의존성 주입
    agent = GeminiAgent(config, jinja_env=jinja_env)
    user_intent = args.intent if args.mode == "CHAT" else None
    
    logger.info(f"워크플로우 시작 (Mode: {args.mode})")

    try:
        # [Separation of Concerns] 워크플로우 실행 (모드에 따라 interactive 설정)
        is_interactive = (args.mode == "CHAT")
        results = await execute_workflow(agent, ocr_text, user_intent, logger, args.ocr_file, args.cand_file, is_interactive)
        
        # [Cost Summary] 비용 정보를 Panel로 표시
        total_cost = agent.get_total_cost()
        cost_info = f"""[bold cyan]💰 Total Session Cost:[/bold cyan] ${total_cost:.4f} USD
[bold green]📊 Token Usage:[/bold green] {agent.total_input_tokens:,} input / {agent.total_output_tokens:,} output"""
        
        console.print()
        console.print(Panel(cost_info, title="[bold blue]Cost Summary[/bold blue]", border_style="blue"))
            
    except Exception as e:
        logger.exception(f"Workflow Failed: {e}")
    finally:
        # [Cleanup] 로그 리스너 종료 (남은 로그 플러시)
        log_listener.stop()

if __name__ == "__main__":
    load_dotenv()
    if os.name == 'nt':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # from rich.console import Console # Already imported at the top
        console.print("\n[bold red][!] 사용자 중단[/bold red]")
        sys.exit(130)
    except Exception as e:
        logging.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)
