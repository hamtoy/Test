# -*- coding: utf-8 -*-
import os
import sys
import logging
import asyncio
import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

# pip install python-dotenv google-generativeai aiofiles pydantic tenacity pydantic-settings jinja2 rich
from dotenv import load_dotenv
import google.generativeai as genai
import aiofiles  # type: ignore[import-untyped]
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from rich.prompt import Confirm

from src.config import AppConfig
from src.agent import GeminiAgent
from src.models import WorkflowResult
from src.data_loader import load_input_data
from src.logging_setup import setup_logging
from src.cache_analytics import analyze_cache_stats, print_cache_report
from src.utils import safe_json_parse, write_cache_stats
from src.exceptions import CacheCreationError

# [Global Console] Rich Console은 전역에서 재사용
# [Global Console] Rich Console은 전역에서 재사용
console = Console()


@dataclass
class WorkflowContext:
    agent: GeminiAgent
    config: AppConfig
    logger: logging.Logger
    ocr_text: str
    candidates: Dict[str, str]
    cache: Any
    total_turns: int
    checkpoint_path: Optional[Path]
    progress: Optional[Progress] = None


async def load_checkpoint(path: Path) -> Dict[str, WorkflowResult]:
    """Load checkpoint entries indexed by query string (async, best-effort)."""
    if not path.exists():
        return {}
    records: Dict[str, WorkflowResult] = {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            async for line in f:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    wf = WorkflowResult(**payload)
                    records[wf.query] = wf
                except Exception:
                    continue
    except Exception:
        return {}
    return records


async def append_checkpoint(path: Path, result: WorkflowResult) -> None:
    """Append a single WorkflowResult to checkpoint JSONL (async, best-effort)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(result.model_dump(), ensure_ascii=False) + "\n")
    except Exception:
        # Non-fatal
        return


async def reload_data_if_needed(
    config: AppConfig, ocr_filename: str, cand_filename: str, interactive: bool = False
) -> tuple[str, Dict[str, str]]:
    """
    [Refactoring] 데이터 로딩 로직 통합
    interactive 모드일 경우 사용자에게 재로딩 여부를 물어볼 수 있게 함 (현재는 로직 단순화로 직접 호출)
    """
    return await load_input_data(config.input_dir, ocr_filename, cand_filename)


def save_result_to_file(result: WorkflowResult, config: AppConfig):
    """[Config Injection] 결과를 Markdown 파일로 저장 (하드코딩 제거)"""
    assert result.evaluation is not None
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
    ctx: WorkflowContext,
    query: str,
    turn_id: int,
) -> Optional[WorkflowResult]:
    ctx.logger.info(f"Turn {turn_id}/{ctx.total_turns}: '{query}' 실행 중...")

    ctx.logger.info("후보 평가 중...")
    evaluation = await ctx.agent.evaluate_responses(
        ctx.ocr_text, query, ctx.candidates, cached_content=ctx.cache
    )
    if evaluation is None:
        ctx.logger.warning(f"Turn {turn_id}: 평가 실패")
        return None

    best_candidate_id = evaluation.get_best_candidate_id()
    ctx.logger.info(f"후보 선정 완료: {best_candidate_id}")

    raw_answer = ctx.candidates.get(best_candidate_id, "")
    parsed = safe_json_parse(raw_answer, best_candidate_id)
    best_answer = parsed if parsed else raw_answer

    ctx.logger.info("답변 재작성 중...")
    rewritten_answer = await ctx.agent.rewrite_best_answer(
        ctx.ocr_text, best_answer, cached_content=None
    )
    ctx.logger.info("답변 재작성 완료")

    return WorkflowResult(
        turn_id=turn_id,
        query=query,
        evaluation=evaluation,
        best_answer=best_answer,
        rewritten_answer=rewritten_answer,
        cost=ctx.agent.get_total_cost(),
        success=True,
    )


async def process_single_query(
    ctx: WorkflowContext,
    query: str,
    turn_id: int,
    task_id: Optional[Any] = None,
) -> Optional[WorkflowResult]:
    """
    [Parallel Processing] 단일 질의 처리 (평가 -> 재작성)
    """
    try:
        # Update progress description
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id, description=f"[cyan]Turn {turn_id}: Processing...[/cyan]"
            )

        result = await _evaluate_and_rewrite_turn(ctx=ctx, query=query, turn_id=turn_id)

        if result:
            # 결과 저장 (Config injection)
            assert result.evaluation is not None
            save_result_to_file(result, ctx.config)
            if ctx.checkpoint_path:
                await append_checkpoint(ctx.checkpoint_path, result)

            # [Rich UI] 턴 결과 출력 (Thread-safe way needed for real app, but Rich handles it reasonably well)
            console.print(
                Panel(
                    f"[bold]Query:[/bold] {query}\n\n"
                    f"[bold]Best Candidate:[/bold] {result.evaluation.get_best_candidate_id()}\n"
                    f"[bold]Rewritten:[/bold] {result.rewritten_answer[:200]}...",
                    title=f"Turn {turn_id} Result",
                    border_style="blue",
                )
            )

            # Mark task as completed
            if ctx.progress and task_id:
                ctx.progress.update(
                    task_id,
                    advance=1,
                    description=f"[green]Turn {turn_id}: Done[/green]",
                )

            return result

    except Exception as e:
        ctx.logger.exception(f"Turn {turn_id} 실행 중 오류 발생: {e}")
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id, description=f"[red]Turn {turn_id}: Failed[/red]"
            )

    return None


async def execute_workflow(
    agent: GeminiAgent,
    ocr_text: str,
    user_intent: Optional[str],
    logger: logging.Logger,
    ocr_filename: str,
    cand_filename: str,
    is_interactive: bool = True,
    resume: bool = False,
    checkpoint_path: Optional[Path] = None,
) -> List[WorkflowResult]:
    """
    [Orchestration] 전체 워크플로우 실행 (Iterative & Human-in-the-Loop)
    """
    # ... (Phase 1: Planning - same as before)
    # [Phase 1: Planning] 질의 리스트 생성
    logger.info("질의 리스트 생성 중...")
    queries = await agent.generate_query(ocr_text, user_intent)

    if not queries:
        logger.error("질의 생성 실패")
        return []

    # [Rich UI] 생성된 질의 리스트 출력
    console.print(
        Panel(
            "\n".join([f"{i + 1}. {q}" for i, q in enumerate(queries)]),
            title="[bold green]Generated Strategic Queries[/bold green]",
            border_style="green",
        )
    )

    # [Conditional Interactivity] AUTO 모드에서는 프롬프트 건너뛰기
    config = AppConfig()  # type: ignore[call-arg]
    candidates: Dict[str, str] = {}  # Initialize candidates
    if checkpoint_path is None:
        checkpoint_path = config.output_dir / "checkpoint.jsonl"
    checkpoint_records: Dict[str, WorkflowResult] = {}
    if resume:
        checkpoint_records = await load_checkpoint(checkpoint_path)
        if checkpoint_records:
            logger.info(
                f"Resume enabled: {len(checkpoint_records)} completed turn(s) preloaded from {checkpoint_path}"
            )

    if is_interactive:
        # [Breakpoint & Hot Reload] 사용자 개입
        if Confirm.ask(
            "위 질의를 보고 후보 답변 파일(input_candidates.json)을 수정하시겠습니까? (수정 후 Enter)",
            default=True,
        ):
            logger.info("사용자 요청으로 데이터 재로딩 중...")
            try:
                _, candidates = await reload_data_if_needed(
                    config, ocr_filename, cand_filename
                )
                logger.info("데이터 재로딩 완료")
            except Exception as e:
                logger.error(f"데이터 재로딩 실패: {e}")
                return []
        else:
            # 재로딩 없이 진행
            _, candidates = await reload_data_if_needed(
                config, ocr_filename, cand_filename
            )
    else:
        # [AUTO Mode] 자동으로 데이터 로드 (프롬프트 없음)
        logger.info("AUTO 모드: 데이터 자동 로딩 중...")
        _, candidates = await reload_data_if_needed(config, ocr_filename, cand_filename)

    # [Context Caching] 캐시 생성 시도
    logger.info("Context Caching 시도 중...")
    try:
        cache = await agent.create_context_cache(ocr_text)
    except CacheCreationError as e:
        cache = None
        logger.warning(f"Context cache creation skipped: {e}")

    # [Phase 2: Execution Loop] 병렬 실행 (Parallel Processing) with Progress Bar
    logger.info(f"총 {len(queries)}개의 질의를 병렬로 처리합니다...")

    results = []

    # Rich Progress Bar Context
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,  # 완료 후 사라짐 (깔끔하게)
    ) as progress:
        tasks = []
        # 전체 진행률 트래킹용 태스크 (선택 사항, 여기서는 개별 태스크만 보여줌)
        # overall_task = progress.add_task("[green]Overall Progress", total=len(queries))

        for i, query in enumerate(queries):
            # Budget check before scheduling turn
            try:
                agent.check_budget()
            except Exception as e:
                logger.error(f"Budget limit exceeded: {e}")
                console.print(
                    Panel(str(e), title="Budget Exceeded", border_style="red")
                )
                break

            usage = agent.get_budget_usage_percent()
            for threshold, severity in [
                (80, "WARNING"),
                (90, "HIGH"),
                (95, "CRITICAL"),
            ]:
                attr_name = f"_warned_{threshold}"
                if usage >= threshold and not hasattr(agent, attr_name):
                    logger.warning(f"{severity}: Budget at {usage:.1f}%")
                    setattr(agent, attr_name, True)

            turn_id = i + 1
            # 각 쿼리별 태스크 생성 (초기 상태: Waiting)
            task_id = progress.add_task(f"[cyan]Turn {turn_id}: Waiting...", total=1)

            if resume and query in checkpoint_records:
                restored = checkpoint_records[query]
                restored.turn_id = turn_id
                results.append(restored)
                if progress and task_id:
                    progress.update(
                        task_id,
                        advance=1,
                        description=f"[green]Turn {turn_id}: Restored[/green]",
                    )
                continue

            tasks.append(
                process_single_query(
                    ctx=WorkflowContext(
                        agent=agent,
                        config=config,
                        logger=logger,
                        ocr_text=ocr_text,
                        candidates=candidates,
                        cache=cache,
                        total_turns=len(queries),
                        checkpoint_path=checkpoint_path,
                        progress=progress,
                    ),
                    query=query,
                    turn_id=turn_id,
                    task_id=task_id,
                )
            )

        # [Concurrency] 모든 태스크 동시 실행 (에러 수집)
        processed_results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

        # None 제거 (실패한 경우)
        results.extend([r for r in processed_results if r is not None and not isinstance(r, Exception)])

        # 예외 로깅
        for exc in processed_results:
            if isinstance(exc, Exception):
                logger.error(f"Turn 실행 중 예외 발생: {exc}")

        # 순서 보장을 위해 turn_id로 정렬 (병렬 처리로 순서가 섞일 수 있음)
        results.sort(key=lambda x: x.turn_id)

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
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,  # Auto-show defaults
    )

    # 1. Core Configuration
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
    core_group.add_argument(
        "--intent",
        type=str,
        default=None,
        help="Optional user intent to guide query generation",
    )
    io_group.add_argument(
        "--checkpoint-file",
        type=str,
        default="checkpoint.jsonl",
        help="Checkpoint JSONL path (relative paths resolve under data/outputs)",
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

    # ... (rest of arguments)

    args = parser.parse_args()

    # ... (logging setup)
    logger, log_listener = setup_logging(log_level=args.log_level)

    # ... (config & resource loading)
    try:
        config = AppConfig()
        genai.configure(api_key=config.api_key)
        # ... (jinja env setup)
        from jinja2 import Environment, FileSystemLoader

        if not config.template_dir.exists():
            raise FileNotFoundError(
                f"Templates directory missing: {config.template_dir}"
            )
        jinja_env = Environment(
            loader=FileSystemLoader(config.template_dir), autoescape=True
        )

        logger.info("리소스 로드 중...")
        input_dir = config.input_dir
        ocr_text, _ = await load_input_data(input_dir, args.ocr_file, args.cand_file)

    except Exception as e:
        # ... (error handling)
        logger.critical(f"[FATAL] Initialization failed: {e}")
        log_listener.stop()
        sys.exit(1)

    # [DI] Agent에 모든 의존성 주입
    agent = GeminiAgent(config, jinja_env=jinja_env)
    user_intent = args.intent if args.mode == "CHAT" else None

    logger.info(f"워크플로우 시작 (Mode: {args.mode})")

    try:
        # Cache analytics quick path
        if args.analyze_cache:
            summary = analyze_cache_stats(config.cache_stats_path)
            print_cache_report(summary)
            log_listener.stop()
            return

        # [Separation of Concerns] 워크플로우 실행 (모드에 따라 interactive 설정)
        # CHAT 모드이거나 --interactive 플래그가 있으면 대화형 모드
        is_interactive = (args.mode == "CHAT") or args.interactive
        checkpoint_path = Path(args.checkpoint_file)
        if not checkpoint_path.is_absolute():
            checkpoint_path = config.output_dir / checkpoint_path

        await execute_workflow(
            agent,
            ocr_text,
            user_intent,
            logger,
            args.ocr_file,
            args.cand_file,
            is_interactive,
            resume=args.resume,
            checkpoint_path=checkpoint_path,
        )

        # ... (rest of main)

        # [Cost Summary] 비용 정보를 Panel로 표시
        total_cost = agent.get_total_cost()
        cost_info = f"""[bold cyan]💰 Total Session Cost:[/bold cyan] ${total_cost:.4f} USD
[bold green]📊 Token Usage:[/bold green] {agent.total_input_tokens:,} input / {agent.total_output_tokens:,} output
[bold magenta]🚀 Cache Stats:[/bold magenta] {agent.cache_hits} hits / {agent.cache_misses} misses"""

        console.print()
        console.print(
            Panel(
                cost_info,
                title="[bold blue]Cost Summary[/bold blue]",
                border_style="blue",
            )
        )

        # [Cache Stats Persistence] append JSONL entry with small retention window
        try:
            cache_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "model": config.model_name,
                "input_tokens": agent.total_input_tokens,
                "output_tokens": agent.total_output_tokens,
                "cache_hits": agent.cache_hits,
                "cache_misses": agent.cache_misses,
            }
            write_cache_stats(
                config.cache_stats_path, config.cache_stats_max_entries, cache_entry
            )
            logger.info(f"Cache stats saved to {config.cache_stats_path}")
        except Exception as e:
            logger.warning(f"Cache stats write skipped: {e}")

    except Exception as e:
        logger.exception(f"Workflow Failed: {e}")
    finally:
        # [Cleanup] 로그 리스너 종료 (남은 로그 플러시)
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
        console.print("\n[bold red][!] 사용자 중단[/bold red]")
        sys.exit(130)
    except Exception as e:
        logging.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)
