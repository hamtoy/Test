# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import sys
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Dict, List, Optional, cast
from types import SimpleNamespace

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.prompt import Confirm

# ============================================================================
# Workflow Execution
# ============================================================================
from src.agent import GeminiAgent
from src.data_loader import load_input_data, reload_data_if_needed

# ============================================================================
# Analytics & Reporting
# ============================================================================
from src.cache_analytics import analyze_cache_stats, print_cache_report
from src.logging_setup import log_metrics, setup_logging

# ============================================================================
# Configuration
# ============================================================================
from src.config import AppConfig
from src.constants import (
    BUDGET_WARNING_THRESHOLDS,
    COST_PANEL_TEMPLATE,
    LOG_MESSAGES,
    PANEL_TITLE_BUDGET,
    PANEL_TITLE_COST,
    PANEL_TITLE_QUERIES,
    PANEL_TURN_BODY_TEMPLATE,
    PANEL_TURN_TITLE_TEMPLATE,
    PROGRESS_DONE_TEMPLATE,
    PROGRESS_FAILED_TEMPLATE,
    PROGRESS_PROCESSING_TEMPLATE,
    PROGRESS_RESTORED_TEMPLATE,
    PROGRESS_WAITING_TEMPLATE,
    PROMPT_EDIT_CANDIDATES,
    USER_INTERRUPT_MESSAGE,
)

# ============================================================================
# CLI Module
# ============================================================================
from src.cli import parse_args, resolve_checkpoint_path

# ============================================================================
# Models & Exceptions
# ============================================================================
from src.models import WorkflowResult
from src.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)

# ============================================================================
# Utilities
# ============================================================================
from src.utils import (
    append_checkpoint,
    load_checkpoint,
    safe_json_parse,
    write_cache_stats,
)

if TYPE_CHECKING:
    from google.generativeai import caching


genai = SimpleNamespace(configure=lambda *_args, **_kwargs: None)

# Rich Console은 전역에서 재사용
console = Console()


@dataclass
class WorkflowContext:
    agent: GeminiAgent
    config: AppConfig
    logger: logging.Logger
    ocr_text: str
    candidates: Dict[str, str]
    cache: Optional["caching.CachedContent"]
    total_turns: int
    checkpoint_path: Optional[Path]
    progress: Optional[Progress] = None


def save_result_to_file(result: WorkflowResult, config: AppConfig) -> None:
    """결과를 Markdown 파일로 저장 (하드코딩 제거)"""
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


def _warn_budget_thresholds(agent: GeminiAgent, logger: logging.Logger) -> None:
    """Emit one-time budget warnings at configured thresholds."""
    usage = agent.get_budget_usage_percent()
    for threshold, severity in BUDGET_WARNING_THRESHOLDS:
        attr_name = "_warned_%s" % threshold
        if usage >= threshold and not hasattr(agent, attr_name):
            logger.warning("%s: Budget at %.1f%%", severity, usage)
            setattr(agent, attr_name, True)


def _display_queries(queries: List[str]) -> None:
    """생성된 질의 리스트를 Rich Panel로 콘솔에 출력합니다.

    Args:
        queries: 출력할 질의 문자열 리스트
    """
    console.print(
        Panel(
            "\n".join([f"{i + 1}. {q}" for i, q in enumerate(queries)]),
            title=PANEL_TITLE_QUERIES,
            border_style="green",
        )
    )


def _render_cost_panel(agent: GeminiAgent) -> Panel:
    """비용, 토큰 사용량, 캐시 통계를 표시하는 Rich Panel을 생성합니다.

    Args:
        agent: 사용량 통계를 포함하는 GeminiAgent 인스턴스

    Returns:
        비용 및 사용량 정보가 설정된 Rich Panel 객체
    """
    cost_fn = getattr(agent, "get_total_cost", None)
    cost_info = COST_PANEL_TEMPLATE.format(
        cost=cost_fn() if callable(cost_fn) else 0.0,
        input_tokens=agent.total_input_tokens,
        output_tokens=agent.total_output_tokens,
        cache_hits=agent.cache_hits,
        cache_misses=agent.cache_misses,
    )
    return Panel(cost_info, title=PANEL_TITLE_COST, border_style="blue")


def _render_budget_panel(agent: GeminiAgent) -> Panel:
    usage_fn = getattr(agent, "get_budget_usage_percent", None)
    usage = usage_fn() if callable(usage_fn) else 0.0
    content = f"Budget usage: {usage:.2f}%"
    return Panel(content, title=PANEL_TITLE_BUDGET, border_style="red")


def _resolve_checkpoint_path(
    config: AppConfig, checkpoint_path: Optional[Path]
) -> Path:
    """체크포인트 파일의 절대 경로를 결정합니다.

    Args:
        config: 애플리케이션 설정 객체
        checkpoint_path: CLI 인자로 제공된 선택적 경로

    Returns:
        체크포인트 파일의 절대 경로
    """
    path = checkpoint_path or (config.output_dir / "checkpoint.jsonl")
    if not path.is_absolute():
        path = config.output_dir / path
    return path


async def _load_checkpoint_records(
    checkpoint_path: Path, resume: bool, logger: logging.Logger
) -> Dict[str, WorkflowResult]:
    """재개 모드가 활성화된 경우 기존 체크포인트 기록을 로드합니다.

    Args:
        checkpoint_path: 체크포인트 파일 경로
        resume: 체크포인트에서 재개 여부를 나타내는 플래그
        logger: 상태 업데이트를 위한 로거 인스턴스

    Returns:
        질의 문자열을 WorkflowResult 객체로 매핑하는 딕셔너리
    """
    if not resume:
        return {}
    records = await load_checkpoint(checkpoint_path)
    if records:
        logger.info(
            f"Resume enabled: {len(records)} completed turn(s) preloaded from {checkpoint_path}"
        )
    return records


async def _load_candidates(
    config: AppConfig,
    ocr_filename: str,
    cand_filename: str,
    is_interactive: bool,
    logger: logging.Logger,
) -> Optional[Dict[str, str]]:
    """후보 답변을 로드하며, 대화형 모드에서는 선택적으로 재로드를 프롬프트합니다.

    Args:
        config: 애플리케이션 설정 객체
        ocr_filename: OCR 입력 파일명
        cand_filename: 후보 답변 입력 파일명
        is_interactive: 대화형 모드 플래그
        logger: 로거 인스턴스

    Returns:
        후보 답변 딕셔너리, 로드 실패 시 None
    """
    if is_interactive and Confirm.ask(PROMPT_EDIT_CANDIDATES, default=True):
        logger.info("사용자 요청으로 데이터 재로딩 중...")
        try:
            _, candidates = await reload_data_if_needed(
                config, ocr_filename, cand_filename
            )
            logger.info("데이터 재로딩 완료")
            return candidates
        except (ValidationFailedError, FileNotFoundError, ValueError) as e:
            logger.error(LOG_MESSAGES["reload_failed"].format(error=e))
            return None

    # 재로딩 없이 진행 (AUTO 또는 skip)
    if not is_interactive:
        logger.info("AUTO 모드: 데이터 자동 로딩 중...")
    else:
        logger.info("재로딩 없이 진행")
    _, candidates = await reload_data_if_needed(config, ocr_filename, cand_filename)
    return candidates


async def _create_context_cache(
    agent: GeminiAgent, ocr_text: str, logger: logging.Logger
) -> Optional["caching.CachedContent"]:
    """OCR 텍스트에 대한 컨텍스트 캐시 생성을 시도합니다.

    Args:
        agent: GeminiAgent 인스턴스
        ocr_text: 캐시할 OCR 텍스트 내용
        logger: 로거 인스턴스

    Returns:
        성공 시 CachedContent 객체, 실패 시 None
    """
    logger.info("Context Caching 시도 중...")
    try:
        return await agent.create_context_cache(ocr_text)
    except CacheCreationError as e:
        logger.warning(LOG_MESSAGES["cache_skipped"].format(error=e))
        return None


def _schedule_turns(
    queries: List[str],
    agent: GeminiAgent,
    config: AppConfig,
    logger: logging.Logger,
    ocr_text: str,
    candidates: Dict[str, str],
    cache: Optional["caching.CachedContent"],
    checkpoint_records: Dict[str, WorkflowResult],
    checkpoint_path: Path,
    progress: Progress,
    resume: bool,
) -> tuple[List[WorkflowResult], List[Awaitable[Optional[WorkflowResult]]]]:
    """턴 작업을 준비하며, 예산 확인, 체크포인트, 진행 표시줄을 처리합니다.

    Args:
        queries: 처리할 질의 리스트
        agent: GeminiAgent 인스턴스
        config: 애플리케이션 설정
        logger: 로거 인스턴스
        ocr_text: OCR 텍스트 내용
        candidates: 후보 답변 딕셔너리
        cache: 선택적 컨텍스트 캐시
        checkpoint_records: 로드된 체크포인트 기록 딕셔너리
        checkpoint_path: 체크포인트 파일 경로
        progress: Rich Progress 인스턴스
        resume: 재개 모드 플래그

    Returns:
        복원된 결과 리스트와 대기 가능한 작업 리스트를 포함하는 Tuple
    """
    results: List[WorkflowResult] = []
    tasks: List[Awaitable[Optional[WorkflowResult]]] = []

    for i, query in enumerate(queries):
        # Budget check before scheduling turn
        try:
            agent.check_budget()
        except BudgetExceededError as e:
            logger.error(LOG_MESSAGES["budget_exceeded"].format(error=e))
            console.print(Panel(str(e), title=PANEL_TITLE_BUDGET, border_style="red"))
            break

        _warn_budget_thresholds(agent, logger)

        turn_id = i + 1
        task_id = progress.add_task(
            PROGRESS_WAITING_TEMPLATE.format(turn_id=turn_id), total=1
        )

        if resume and query in checkpoint_records:
            restored = checkpoint_records[query]
            restored.turn_id = turn_id
            results.append(restored)
            progress.update(
                task_id,
                advance=1,
                description=PROGRESS_RESTORED_TEMPLATE.format(turn_id=turn_id),
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

    return results, tasks


async def _gather_results(
    tasks: List[Awaitable[Optional[WorkflowResult]]],
    logger: logging.Logger,
) -> List[WorkflowResult]:
    """Execute scheduled tasks and collect successful results.

    Args:
        tasks: List of awaitable tasks returning Optional[WorkflowResult].
        logger: Logger instance.

    Returns:
        List of successfully completed WorkflowResult objects.
    """
    if not tasks:
        return []

    filtered: List[WorkflowResult] = []
    first_error: Optional[Exception] = None
    processed_results = await asyncio.gather(*tasks, return_exceptions=True)
    for item in processed_results:
        if isinstance(item, BudgetExceededError):
            # 예산 초과는 즉시 상위로 전파하여 추가 실행을 막는다.
            raise item
        if isinstance(item, Exception):
            logger.error(LOG_MESSAGES["turn_exception"].format(error=item))
            first_error = first_error or item
            continue
        if item is None:
            continue
        filtered.append(cast(WorkflowResult, item))
    if first_error:
        raise first_error
    return filtered


async def _evaluate_and_rewrite_turn(
    ctx: WorkflowContext,
    query: str,
    turn_id: int,
) -> Optional[WorkflowResult]:
    ctx.logger.info("Turn %s/%s: '%s' 실행 중...", turn_id, ctx.total_turns, query)

    ctx.logger.info("후보 평가 중...")
    evaluation = await ctx.agent.evaluate_responses(
        ctx.ocr_text, query, ctx.candidates, cached_content=ctx.cache
    )
    if evaluation is None:
        ctx.logger.warning("Turn %s: 평가 실패", turn_id)
        return None

    best_candidate_id = evaluation.get_best_candidate_id()
    ctx.logger.info("후보 선정 완료: %s", best_candidate_id)

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
    단일 질의 처리 (평가 -> 재작성)
    """
    try:
        # Update progress description
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id,
                description=PROGRESS_PROCESSING_TEMPLATE.format(turn_id=turn_id),
            )

        result = await _evaluate_and_rewrite_turn(ctx=ctx, query=query, turn_id=turn_id)

        if result:
            # 결과 저장
            assert result.evaluation is not None
            save_result_to_file(result, ctx.config)
            if ctx.checkpoint_path:
                await append_checkpoint(ctx.checkpoint_path, result)

            # 턴 결과 출력 (Thread-safe way needed for real app, but Rich handles it reasonably well)
            console.print(
                Panel(
                    PANEL_TURN_BODY_TEMPLATE.format(
                        query=query,
                        best_candidate=result.evaluation.get_best_candidate_id(),
                        rewritten=result.rewritten_answer[:200],
                    ),
                    title=PANEL_TURN_TITLE_TEMPLATE.format(turn_id=turn_id),
                    border_style="blue",
                )
            )

            # Mark task as completed
            if ctx.progress and task_id:
                ctx.progress.update(
                    task_id,
                    advance=1,
                    description=PROGRESS_DONE_TEMPLATE.format(turn_id=turn_id),
                )

            return result

    except (APIRateLimitError, ValidationFailedError, SafetyFilterError) as e:
        ctx.logger.error("복구 가능 오류로 턴 %s를 건너뜁니다: %s", turn_id, e)
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id,
                description=PROGRESS_FAILED_TEMPLATE.format(turn_id=turn_id),
            )
        return None
    except BudgetExceededError as e:
        ctx.logger.critical("예산 초과로 워크플로우를 중단합니다: %s", e)
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id,
                description=PROGRESS_FAILED_TEMPLATE.format(turn_id=turn_id),
            )
        raise
    except (OSError, RuntimeError) as e:
        ctx.logger.exception(LOG_MESSAGES["turn_exception"].format(error=e))
        if ctx.progress and task_id:
            ctx.progress.update(
                task_id,
                description=PROGRESS_FAILED_TEMPLATE.format(turn_id=turn_id),
            )

    return None


async def execute_workflow(
    agent: GeminiAgent,
    ocr_text: str,
    user_intent: Optional[str],
    logger: logging.Logger,
    ocr_filename: str,
    cand_filename: str,
    config: Optional[AppConfig] = None,
    is_interactive: bool = True,
    resume: bool = False,
    checkpoint_path: Optional[Path] = None,
    keep_progress: bool = False,
) -> List[WorkflowResult]:
    """전체 워크플로우 실행 (질의 생성 → 평가 → 재작성).

    단계:
    1. 질의 생성: OCR + 사용자 의도 기반
    2. 대화형 모드: 후보 답변 수정 가능 (선택)
    3. 병렬 평가: 각 질의에 대해 후보 평가 및 재작성
    4. 체크포인트: 완료된 질의는 재실행 건너뜀

    Args:
        agent: Gemini API 에이전트
        ocr_text: 입력 OCR 텍스트
        user_intent: 사용자 의도 (선택)
        logger: 로거 인스턴스
        ocr_filename: OCR 파일명 (재로딩용)
        cand_filename: 후보 파일명 (재로딩용)
        is_interactive: 대화형 모드 활성화 여부
        resume: 체크포인트 복구 여부
        checkpoint_path: 체크포인트 파일 경로
        keep_progress: 완료 후에도 Progress Bar를 유지할지 여부

    Returns:
        각 질의별 평가 결과 리스트
    """
    # ... (Phase 1: Planning - same as before)
    # 질의 리스트 생성
    logger.info("질의 리스트 생성 중...")
    queries = await agent.generate_query(ocr_text, user_intent)

    if not queries:
        logger.error("질의 생성 실패")
        return []

    # 생성된 질의 리스트 출력
    _display_queries(queries)

    # AUTO 모드에서는 프롬프트 건너뛰기
    config = config or AppConfig()  # type: ignore[call-arg]
    candidates: Optional[Dict[str, str]] = None
    checkpoint_path = _resolve_checkpoint_path(config, checkpoint_path)
    checkpoint_records = await _load_checkpoint_records(checkpoint_path, resume, logger)

    candidates = await _load_candidates(
        config=config,
        ocr_filename=ocr_filename,
        cand_filename=cand_filename,
        is_interactive=is_interactive,
        logger=logger,
    )
    if candidates is None:
        return []

    # 캐시 생성 시도 (Context Caching)
    cache = await _create_context_cache(agent, ocr_text, logger)

    # 병렬 실행 (Parallel Processing) with Progress Bar
    logger.info("총 %s개의 질의를 병렬로 처리합니다...", len(queries))

    results: List[WorkflowResult] = []

    # Rich Progress Bar Context
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=not keep_progress,  # 디버깅 시 기록 유지 옵션
    ) as progress:
        restored_results, tasks = _schedule_turns(
            queries=queries,
            agent=agent,
            config=config,
            logger=logger,
            ocr_text=ocr_text,
            candidates=candidates,
            cache=cache,
            checkpoint_records=checkpoint_records,
            checkpoint_path=checkpoint_path,
            progress=progress,
            resume=resume,
        )
        results.extend(restored_results)

        # 모든 태스크 동시 실행 (에러 수집)
        results.extend(await _gather_results(tasks, logger))

        # 순서 보장을 위해 turn_id로 정렬 (병렬 처리로 순서가 섞일 수 있음)
        results.sort(key=lambda x: x.turn_id)

    # 캐시 삭제 (Cleanup)
    if cache:
        try:
            cache.delete()
            logger.info("Cache cleaned up: %s", cache.name)
        except (OSError, RuntimeError) as e:
            logger.warning("Cache cleanup failed: %s", e)

    return results


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
        checkpoint_path = resolve_checkpoint_path(config.output_dir, args.checkpoint_file)

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
            console.print(_render_budget_panel(agent))
        if not args.no_cost_panel:
            console.print(_render_cost_panel(agent))

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

