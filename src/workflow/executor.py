"""워크플로우 실행 오케스트레이터."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Dict, List, Optional, cast

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.prompt import Confirm

from src.config import AppConfig
from src.constants import (
    LOG_MESSAGES,
    PANEL_TITLE_BUDGET,
    PROGRESS_RESTORED_TEMPLATE,
    PROGRESS_WAITING_TEMPLATE,
    PROMPT_EDIT_CANDIDATES,
)
from src.processing.loader import reload_data_if_needed
from src.exceptions import (
    BudgetExceededError,
    CacheCreationError,
    ValidationFailedError,
)
from src.models import WorkflowResult
from src.ui import console
from src.utils import load_checkpoint

from .context import WorkflowContext
from .processor import process_single_query

if TYPE_CHECKING:
    from google.generativeai import caching

    from src.agent import GeminiAgent


def _warn_budget_thresholds(agent: GeminiAgent, logger: logging.Logger) -> None:
    """Emit one-time budget warnings at configured thresholds."""
    from src.constants import BUDGET_WARNING_THRESHOLDS

    usage = agent.get_budget_usage_percent()
    for threshold, severity in BUDGET_WARNING_THRESHOLDS:
        attr_name = "_warned_%s" % threshold
        if usage >= threshold and not hasattr(agent, attr_name):
            logger.warning("%s: Budget at %.1f%%", severity, usage)
            setattr(agent, attr_name, True)


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
) -> Optional[caching.CachedContent]:
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
    cache: Optional[caching.CachedContent],
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
        config: 애플리케이션 설정 (기본값: None)
        is_interactive: 대화형 모드 활성화 여부
        resume: 체크포인트 복구 여부
        checkpoint_path: 체크포인트 파일 경로
        keep_progress: 완료 후에도 Progress Bar를 유지할지 여부

    Returns:
        각 질의별 평가 결과 리스트
    """
    from src.ui import display_queries

    # 질의 리스트 생성
    logger.info("질의 리스트 생성 중...")
    queries = await agent.generate_query(ocr_text, user_intent)

    if not queries:
        logger.error("질의 생성 실패")
        return []

    # 생성된 질의 리스트 출력
    display_queries(queries)

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
