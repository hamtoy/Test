"""개별 턴 처리."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from rich.panel import Panel

from src.config.constants import (
    LOG_MESSAGES,
    PANEL_TURN_BODY_TEMPLATE,
    PANEL_TURN_TITLE_TEMPLATE,
    PROGRESS_DONE_TEMPLATE,
    PROGRESS_FAILED_TEMPLATE,
    PROGRESS_PROCESSING_TEMPLATE,
)
from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.core.models import WorkflowResult
from src.infra.utils import append_checkpoint, safe_json_parse
from src.ui.panels import console

from .context import WorkflowContext


def save_result_to_file(result: WorkflowResult, config: Any) -> None:
    """결과를 Markdown 파일로 저장 (하드코딩 제거)."""
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
) -> WorkflowResult | None:
    """평가 및 재작성 실행."""
    ctx.logger.info("Turn %s/%s: '%s' 실행 중...", turn_id, ctx.total_turns, query)

    ctx.logger.info("후보 평가 중...")
    evaluation = await ctx.agent.evaluate_responses(
        ctx.ocr_text,
        query,
        ctx.candidates,
        cached_content=ctx.cache,
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
        ctx.ocr_text,
        best_answer,
        cached_content=None,
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


def _update_progress_if_available(
    ctx: WorkflowContext,
    task_id: Any | None,
    **kwargs: Any,
) -> None:
    if ctx.progress and task_id:
        ctx.progress.update(task_id, **kwargs)


def _mark_turn_failed(ctx: WorkflowContext, task_id: Any | None, turn_id: int) -> None:
    _update_progress_if_available(
        ctx,
        task_id,
        description=PROGRESS_FAILED_TEMPLATE.format(turn_id=turn_id),
    )


async def _persist_turn_result(
    ctx: WorkflowContext,
    result: WorkflowResult,
) -> None:
    assert result.evaluation is not None
    save_result_to_file(result, ctx.config)
    if ctx.checkpoint_path:
        await append_checkpoint(ctx.checkpoint_path, result)


def _print_turn_panel(query: str, result: WorkflowResult, turn_id: int) -> None:
    assert result.evaluation is not None
    console.print(
        Panel(
            PANEL_TURN_BODY_TEMPLATE.format(
                query=query,
                best_candidate=result.evaluation.get_best_candidate_id(),
                rewritten=result.rewritten_answer[:200],
            ),
            title=PANEL_TURN_TITLE_TEMPLATE.format(turn_id=turn_id),
            border_style="blue",
        ),
    )


async def process_single_query(
    ctx: WorkflowContext,
    query: str,
    turn_id: int,
    task_id: Any | None = None,
) -> WorkflowResult | None:
    """단일 질의 처리 (평가 → 재작성)."""
    _update_progress_if_available(
        ctx,
        task_id,
        description=PROGRESS_PROCESSING_TEMPLATE.format(turn_id=turn_id),
    )
    try:
        result = await _evaluate_and_rewrite_turn(ctx=ctx, query=query, turn_id=turn_id)
    except (APIRateLimitError, ValidationFailedError, SafetyFilterError) as exc:
        ctx.logger.error("복구 가능 오류로 턴 %s를 건너뜁니다: %s", turn_id, exc)
        _mark_turn_failed(ctx, task_id, turn_id)
        return None
    except BudgetExceededError as exc:
        ctx.logger.critical("예산 초과로 워크플로우를 중단합니다: %s", exc)
        _mark_turn_failed(ctx, task_id, turn_id)
        raise
    except (OSError, RuntimeError) as exc:
        ctx.logger.exception(LOG_MESSAGES["turn_exception"].format(error=exc))
        _mark_turn_failed(ctx, task_id, turn_id)
        return None

    if not result:
        return None

    await _persist_turn_result(ctx, result)
    _print_turn_panel(query, result, turn_id)
    _update_progress_if_available(
        ctx,
        task_id,
        advance=1,
        description=PROGRESS_DONE_TEMPLATE.format(turn_id=turn_id),
    )
    return result
