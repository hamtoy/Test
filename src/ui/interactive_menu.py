"""Interactive Menu UI for Gemini Workflow System."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.caching.analytics import analyze_cache_stats, print_cache_report
from src.caching.redis_cache import RedisEvalCache
from src.config import AppConfig
from src.config.constants import (
    QUERY_PREVIEW_MAX_LENGTH,
    QUERY_PREVIEW_TRUNCATE_LENGTH,
)
from src.core.models import WorkflowResult
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.features.lats import LATSSearcher
from src.processing.loader import load_input_data
from src.qa.rag_system import QAKnowledgeGraph
from src.ui.panels import (
    console,
    display_queries,
    render_budget_panel,
    render_cost_panel,
)
from src.workflow.edit import edit_content
from src.workflow.executor import execute_workflow_simple
from src.workflow.inspection import inspect_answer, inspect_query

# Constants
MENU_CHOICES = ["1", "2", "3", "4", "5"]
DEFAULT_OCR_PATH = "data/inputs/input_ocr.txt"
RETURN_TO_MENU_PROMPT = "엔터를 눌러 메뉴로 돌아갑니다"
PROGRESS_DESCRIPTION_TEMPLATE = "[progress.description]{task.description}"
STATUS_DONE = "[green]✓ 완료[/green]"


def _load_non_empty_file(
    prompt_label: str,
    *,
    missing_message: str,
    empty_message: str,
) -> str | None:
    file_str = Prompt.ask(prompt_label)
    file_path = Path(file_str.strip())
    if not file_path.exists():
        console.print(missing_message.format(path=file_path))
        return None
    text = file_path.read_text(encoding="utf-8")
    if not text.strip():
        console.print(empty_message)
        return None
    return text


def _load_optional_ocr_text(prompt_when_missing: str) -> str:
    ocr_file = Path(DEFAULT_OCR_PATH)
    if ocr_file.exists():
        console.print(f"[dim]📄 OCR 자동 로드: {ocr_file}[/dim]")
        try:
            return ocr_file.read_text(encoding="utf-8")
        except OSError as exc:  # noqa: PERF203
            console.print(f"[yellow]OCR 로드 실패: {exc}[/yellow]")
            return ""

    ocr_path_input = Prompt.ask(prompt_when_missing, default="")
    if not ocr_path_input:
        return ""

    ocr_path = Path(ocr_path_input.strip())
    if not ocr_path.exists():
        console.print(f"[yellow]OCR 파일을 찾을 수 없습니다: {ocr_path}[/yellow]")
        return ""

    return ocr_path.read_text(encoding="utf-8")


def _prompt_optional_query(question_label: str, query_label: str) -> str:
    if Prompt.ask(question_label, choices=["y", "n"], default="n").lower() != "y":
        return ""
    return Prompt.ask(query_label)


def _init_answer_inspection_resources(
    agent: GeminiAgent,
    config: AppConfig,
) -> tuple[
    QAKnowledgeGraph | None,
    LATSSearcher | None,
    CrossValidationSystem | None,
    RedisEvalCache | None,
]:
    kg = QAKnowledgeGraph() if config.neo4j_uri else None
    lats = LATSSearcher(agent.llm_provider) if config.enable_lats else None
    validator = CrossValidationSystem(kg) if kg else None
    cache = RedisEvalCache() if os.getenv("REDIS_URL") else None
    return kg, lats, validator, cache


def show_error_with_guide(error_type: str, message: str, solution: str) -> None:
    """에러 메시지 + 해결 방법 표시."""
    console.print(f"\n[red]✗ {error_type}: {message}[/red]")
    console.print(f"[dim]💡 해결 방법: {solution}[/dim]\n")


def show_main_menu() -> int:
    """메인 메뉴 - 기능 플래그 상태 표시 포함."""
    console.clear()

    # 기능 플래그 자동 감지
    flags = []
    if os.getenv("NEO4J_URI"):
        flags.append("[green]Neo4j ✓[/green]")
    if os.getenv("ENABLE_LATS", "").lower() == "true":
        flags.append("[yellow]LATS ✓[/yellow]")
    if os.getenv("ENABLE_DATA2NEO", "").lower() == "true":
        flags.append("[blue]Data2Neo ✓[/blue]")
    if os.getenv("REDIS_URL"):
        flags.append("[cyan]Redis ✓[/cyan]")

    status = " | ".join(flags) if flags else "[dim]기본 모드[/dim]"

    console.print("\n[bold cyan]═══ Gemini Workflow System ═══[/bold cyan]")
    console.print("[dim]규칙 준수 리라이팅 · 검수 반려 방지[/dim]")
    console.print(f"\n상태: {status}\n")

    console.print("1. 🔄 질의 생성 및 평가")
    console.print("2. ✅ 검수 (질의/답변)")
    console.print("3. ✏️ 수정 (사용자 요청 기반 재작성)")
    console.print("4. 📊 캐시 통계 분석")
    console.print("5. 🚪 종료\n")

    choice = Prompt.ask("선택", choices=MENU_CHOICES, default="1")
    return int(choice) - 1


async def run_workflow_interactive(
    agent: GeminiAgent,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    """질의 생성 및 평가 - 에러 핸들링 강화."""
    if not _ensure_valid_api_key(config):
        return

    ocr_file, cand_file = _prompt_workflow_input_files()
    ocr_path, cand_path = _resolve_input_paths(config, ocr_file, cand_file)

    if not _ensure_ocr_file(ocr_path):
        return
    if not _ensure_candidate_file(cand_path):
        return

    loaded = await _load_workflow_inputs(config, ocr_file, cand_file)
    if loaded is None:
        return
    ocr_text, candidates = loaded

    user_intent = Prompt.ask("사용자 의도 (선택)", default="")
    queries = await _generate_queries_with_progress(agent, ocr_text, user_intent)
    if not queries:
        console.print("[yellow]생성된 질의가 없습니다.[/yellow]")
        return

    display_queries(queries)
    if not _confirm_queries():
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = await _execute_queries_with_progress(
        queries,
        agent,
        ocr_text,
        candidates,
        config,
        logger,
    )
    _display_workflow_summary(queries, results, agent, config, timestamp)
    Prompt.ask(f"\n{RETURN_TO_MENU_PROMPT}")


def _ensure_valid_api_key(config: AppConfig) -> bool:
    if config.api_key and config.api_key.startswith("AIza"):
        return True
    show_error_with_guide(
        "API 키가 유효하지 않습니다",
        "GEMINI_API_KEY가 설정되지 않았거나 형식이 올바르지 않습니다",
        ".env 파일에서 GEMINI_API_KEY='AIza...'로 시작하는 키를 설정하세요",
    )
    Prompt.ask(RETURN_TO_MENU_PROMPT)
    return False


def _prompt_workflow_input_files() -> tuple[str, str]:
    ocr_file = Prompt.ask("OCR 파일명", default="input_ocr.txt")
    cand_file = Prompt.ask("후보 답변 파일명", default="input_candidates.json")
    return ocr_file, cand_file


def _resolve_input_paths(
    config: AppConfig,
    ocr_file: str,
    cand_file: str,
) -> tuple[Path, Path]:
    return config.input_dir / ocr_file, config.input_dir / cand_file


def _ensure_ocr_file(ocr_path: Path) -> bool:
    if ocr_path.exists():
        return True
    console.print(f"[red]✗ OCR 파일이 없습니다: {ocr_path}[/red]")
    if not Confirm.ask("빈 파일을 생성할까요?", default=True):
        return False
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    ocr_path.write_text("", encoding="utf-8")
    console.print("[green]✓ 파일 생성됨 - IDE에서 내용을 입력하세요[/green]")
    return True


def _ensure_candidate_file(cand_path: Path) -> bool:
    if cand_path.exists():
        return True
    console.print(f"[red]✗ 후보 답변 파일이 없습니다: {cand_path}[/red]")
    if not Confirm.ask("템플릿을 생성할까요?", default=True):
        return False
    import json

    template = {"a": "첫 번째 답변", "b": "두 번째 답변", "c": "세 번째 답변"}
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print("[green]✓ 템플릿 생성됨 - IDE에서 답변을 입력하세요[/green]")
    return True


async def _load_workflow_inputs(
    config: AppConfig,
    ocr_file: str,
    cand_file: str,
) -> tuple[str, dict[str, str]] | None:
    try:
        return await load_input_data(config.input_dir, ocr_file, cand_file)
    except FileNotFoundError as exc:
        show_error_with_guide(
            "파일을 찾을 수 없습니다",
            str(exc),
            "IDE에서 data/inputs/ 폴더에 파일을 생성하세요",
        )
        Prompt.ask(RETURN_TO_MENU_PROMPT)
        return None
    except Exception as exc:  # noqa: BLE001
        import json

        if isinstance(getattr(exc, "__cause__", None), json.JSONDecodeError):
            show_error_with_guide(
                "JSON 파싱 오류",
                "후보 답변 파일 형식이 올바르지 않습니다",
                '올바른 형식: {"a": "답변1", "b": "답변2", "c": "답변3"}',
            )
        else:
            show_error_with_guide(
                "데이터 로드 실패",
                str(exc),
                "파일 경로와 형식을 확인하세요",
            )
        Prompt.ask(RETURN_TO_MENU_PROMPT)
        return None


async def _generate_queries_with_progress(
    agent: GeminiAgent,
    ocr_text: str,
    user_intent: str,
) -> list[str]:
    with Progress(
        SpinnerColumn(),
        TextColumn(PROGRESS_DESCRIPTION_TEMPLATE),
        console=console,
    ) as progress:
        task = progress.add_task("전략적 질의 생성 중...", total=None)
        try:
            queries = await agent.generate_query(ocr_text, user_intent or None)
            progress.update(task, description="[green]✓ 질의 생성 완료[/green]")
            return queries
        except Exception as exc:  # noqa: BLE001
            progress.update(task, description="[red]✗ 질의 생성 실패[/red]")
            show_error_with_guide(
                "질의 생성 실패",
                str(exc),
                "API 키와 네트워크 연결을 확인하고 다시 시도하세요",
            )
            Prompt.ask(RETURN_TO_MENU_PROMPT)
            return []


def _confirm_queries() -> bool:
    if Confirm.ask("위 질의들로 진행하시겠습니까?", default=True):
        return True
    console.print("[yellow]작업이 취소되었습니다.[/yellow]")
    return False


async def _execute_queries_with_progress(
    queries: list[str],
    agent: GeminiAgent,
    ocr_text: str,
    candidates: dict[str, str],
    config: AppConfig,
    logger: logging.Logger,
) -> list[WorkflowResult | None]:
    console.print(f"\n[bold]⚙️  {len(queries)}개 질의 처리 시작[/bold]\n")
    results: list[WorkflowResult | None] = []
    with Progress(
        SpinnerColumn(),
        TextColumn(PROGRESS_DESCRIPTION_TEMPLATE),
        console=console,
    ) as progress:
        for idx, query in enumerate(queries):
            turn_id = idx + 1
            task = progress.add_task(
                f"[cyan]질의 {turn_id}/{len(queries)}: {query[:QUERY_PREVIEW_MAX_LENGTH]}...[/cyan]",
                total=None,
            )
            try:
                result = await execute_workflow_simple(
                    agent=agent,
                    ocr_text=ocr_text,
                    candidates=candidates,
                    config=config,
                    logger=logger,
                    query=query,
                    turn_id=turn_id,
                )
                results.append(result)
                _update_workflow_progress(progress, task, turn_id, len(queries), result)
            except Exception:  # noqa: BLE001
                logger.exception("Query %d failed", turn_id)
                progress.update(
                    task,
                    description=f"[red]✗ 질의 {turn_id}/{len(queries)} 실패[/red]",
                )
                results.append(None)
    return results


def _update_workflow_progress(
    progress: Progress,
    task_id: TaskID,
    turn_id: int,
    total_turns: int,
    result: WorkflowResult | None,
) -> None:
    if result and result.success:
        progress.update(
            task_id,
            description=f"[green]✓ 질의 {turn_id}/{total_turns} 완료[/green]",
        )
        return
    progress.update(
        task_id,
        description=f"[yellow]⚠ 질의 {turn_id}/{total_turns} 건너뜀[/yellow]",
    )


async def _handle_query_inspection(agent: GeminiAgent, config: AppConfig) -> None:
    """질의 검수 핸들러 (Direct Input -> CLI Output).

    UX 원칙:
    - 질의 직접 입력 (복붙)
    - OCR 자동 로드 (난이도 분석용)
    - 결과 즉시 CLI 출력 (패널)
    """
    console.print(Panel("✅ 질의 검수 모드", style="cyan"))

    # [1] 질의 직접 입력
    query_input = Prompt.ask("\n❓ 질의 입력 (복붙)")
    if not query_input.strip():
        console.print("[yellow]질의가 입력되지 않았습니다.[/yellow]")
        return

    # [2] OCR 자동 로드 (난이도 분석용)
    ocr_text = ""
    ocr_file = Path(DEFAULT_OCR_PATH)
    if ocr_file.exists():
        console.print(f"[dim]📄 OCR 자동 로드: {ocr_file}[/dim]")
        ocr_text = ocr_file.read_text(encoding="utf-8")
    else:
        console.print(f"[dim]OCR 파일 없음: {ocr_file} (난이도 분석 생략)[/dim]")

    # 리소스 초기화
    kg = QAKnowledgeGraph() if config.neo4j_uri else None
    lats = LATSSearcher(agent.llm_provider) if config.enable_lats else None
    difficulty = AdaptiveDifficultyAdjuster(kg) if kg else None
    cache: RedisEvalCache | None = None
    if os.getenv("REDIS_URL"):
        cache = RedisEvalCache()

    try:
        # [3] 실행 & 출력
        with Progress(
            SpinnerColumn(),
            TextColumn(PROGRESS_DESCRIPTION_TEMPLATE),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]최적화 중...", total=None)

            # Context 구성
            context = {"type": "general"}

            fixed_query = await inspect_query(
                agent,
                query_input,
                ocr_text,
                context,
                kg,
                lats,
                difficulty,
                cache,
            )

            progress.update(task, completed=100, description=STATUS_DONE)

        # 결과 즉시 출력 (패널)
        result_content = (
            f"[dim]원본: {query_input}[/dim]\n\n"
            f"[bold green]수정: {fixed_query}[/bold green]"
        )
        console.print(Panel(result_content, title="✅ 검수 결과", border_style="green"))

    except Exception as e:
        console.print(f"[red]검수 실패: {e}[/red]")
    finally:
        if kg:
            kg.close()


async def _handle_answer_inspection(agent: GeminiAgent, config: AppConfig) -> None:
    """답변 검수 핸들러 (File Input -> File Output).

    UX 원칙:
    - 파일 경로 입력 (긴 텍스트)
    - OCR 자동 로드 (사실 검증용)
    - 결과 파일 저장 (CLI 출력 없음)
    """
    console.print(Panel("✅ 답변 검수 모드", style="cyan"))

    # [1] 파일 입력
    answer = _load_non_empty_file(
        "\n📂 답변 파일 경로",
        missing_message="[red]파일이 존재하지 않습니다: {path}[/red]",
        empty_message="[yellow]답변 파일이 비어있습니다.[/yellow]",
    )
    if answer is None:
        return

    # [2] OCR 자동 로드 (사실 검증용)
    ocr_text = _load_optional_ocr_text("OCR 파일 경로")

    # [3] 질의 여부 (선택)
    query = _prompt_optional_query("❓ 질의 입력?", "   질의")

    kg, lats, validator, cache = _init_answer_inspection_resources(agent, config)

    try:
        # [4] 실행 & 저장 (CLI 출력 X)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/outputs")
        output_path = output_dir / f"inspected_{timestamp}.md"

        with Progress(
            SpinnerColumn(),
            TextColumn(PROGRESS_DESCRIPTION_TEMPLATE),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]검수 및 수정 중...", total=None)

            context = {"type": "general", "image_meta": {}}

            fixed_answer = await inspect_answer(
                agent,
                answer,
                query,
                ocr_text,
                context,
                kg,
                lats,
                validator,
                cache,
            )

            # 결과 저장
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(fixed_answer, encoding="utf-8")

            progress.update(task, completed=100, description=STATUS_DONE)

        console.print("\n✅ [bold green]완료[/bold green]")
        console.print(f"💾 저장됨: {output_path}")

    except Exception as e:
        console.print(f"[red]검수 실패: {e}[/red]")
    finally:
        if kg:
            kg.close()


async def _handle_edit_menu(agent: GeminiAgent, config: AppConfig) -> None:
    """수정 메뉴 핸들러 (사용자 요청 기반 재작성).

    UX 원칙:
    - 답변 파일 입력
    - OCR 자동 로드
    - 질의 선택 입력
    - 간결한 수정 요청 한 줄 입력
    - 결과 파일 저장 (CLI 출력 없음)
    """
    console.print(Panel("✏️ 수정 모드: 간결한 요청으로 내용 재작성", style="cyan"))

    # [1] 답변 파일 입력
    answer_text = _load_non_empty_file(
        "\n📂 수정할 답변 파일 경로",
        missing_message="[red]❌ 파일을 찾을 수 없습니다: {path}[/red]",
        empty_message="[yellow]답변 파일이 비어있습니다.[/yellow]",
    )
    if answer_text is None:
        return

    # [2] OCR 자동 로드
    ocr_text = _load_optional_ocr_text("📄 OCR 파일 경로 (없으면 Enter)")
    if not ocr_text:
        console.print("[dim]⚠ OCR 텍스트 없음 (컨텍스트 없이 수정합니다)[/dim]")

    # [3] 질의 입력 (선택)
    query = _prompt_optional_query("❓ 질의를 문맥에 포함할까요?", "   ❓ 질의 내용")

    # [4] 수정 요청 입력 (핵심)
    edit_request = Prompt.ask("\n✏️ 어떻게 수정할까요? (한 줄)")
    if not edit_request.strip():
        console.print("[red]❌ 수정 요청이 없습니다.[/red]")
        return

    # 리소스 초기화
    kg = QAKnowledgeGraph() if config.neo4j_uri else None

    try:
        # [5] 수정 실행
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/outputs")
        output_path = output_dir / f"edited_{timestamp}.md"

        with Progress(
            SpinnerColumn(),
            TextColumn(PROGRESS_DESCRIPTION_TEMPLATE),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]요청에 따라 내용 수정 중...", total=None)

            edited_text = await edit_content(
                agent=agent,
                answer=answer_text,
                ocr_text=ocr_text,
                query=query,
                edit_request=edit_request.strip(),
                kg=kg,
            )

            # 결과 저장
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(edited_text, encoding="utf-8")

            progress.update(task, completed=100, description=STATUS_DONE)

        console.print("\n✅ [bold green]수정 완료[/bold green]")
        console.print(f"💾 저장됨: {output_path}")

    except Exception as e:
        console.print(f"[red]❌ 수정 중 오류 발생: {e}[/red]")
    finally:
        if kg:
            kg.close()


def show_cache_statistics(config: AppConfig) -> None:
    """캐시 통계 분석."""
    console.print("\n[bold]캐시 통계 분석[/bold]")
    try:
        summary = analyze_cache_stats(config.cache_stats_path)
        print_cache_report(summary)
    except Exception as e:
        console.print(f"[red]통계 분석 실패: {e}[/red]")
    Prompt.ask(RETURN_TO_MENU_PROMPT)


def _display_workflow_summary(
    queries: list[str],
    results: list[WorkflowResult | None],
    agent: GeminiAgent,
    config: AppConfig,
    timestamp: str,
) -> None:
    """워크플로우 완료 후 결과 요약 표시."""
    console.print("\n[bold green]═══ 워크플로우 완료 ═══[/bold green]\n")

    # 처리 결과 테이블
    table = Table(title="처리 결과")
    table.add_column("#", style="cyan", width=3)
    table.add_column("질의", style="white", max_width=50)
    table.add_column("상태", style="green", width=8)
    table.add_column("결과 파일", style="blue", max_width=30)

    success_count = 0
    for i, (query, result) in enumerate(zip(queries, results), 1):
        if result and result.success:
            output_file = f"result_turn_{i}_{timestamp}.md"
            status = STATUS_DONE
            success_count += 1
        else:
            output_file = "-"
            status = "[red]✗ 실패[/red]"

        # 질의 텍스트 잘라내기
        query_display = (
            query[:QUERY_PREVIEW_TRUNCATE_LENGTH] + "..."
            if len(query) > QUERY_PREVIEW_MAX_LENGTH
            else query
        )
        table.add_row(str(i), query_display, status, output_file)

    console.print(table)

    # 통계 정보
    console.print(f"\n[bold]성공: {success_count}/{len(queries)}[/bold]")
    logging.getLogger(__name__).debug(
        "Workflow summary generated: %d/%d success (cache_dir=%s)",
        success_count,
        len(queries),
        config.local_cache_dir,
    )

    # 비용/토큰 정보 (Budget Panel 통합)
    console.print()
    console.print(render_budget_panel(agent))
    console.print(render_cost_panel(agent))


async def interactive_main(
    agent: GeminiAgent,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    """대화형 메인 루프."""
    while True:
        try:
            choice = show_main_menu()
            await _handle_main_menu_choice(choice, agent, config, logger)
        except KeyboardInterrupt:  # noqa: PERF203
            if _confirm_return_to_menu():
                continue
        except Exception as exc:  # noqa: BLE001
            _handle_interactive_exception(exc, logger)


def _exit_interactive() -> NoReturn:
    console.print("[bold]시스템을 종료합니다. 안녕히 가세요! 👋[/bold]")
    sys.exit(0)


async def _handle_inspection_menu(agent: GeminiAgent, config: AppConfig) -> None:
    sub_choice = Prompt.ask(
        "검수 유형 선택 (1: 질의, 2: 답변)",
        choices=["1", "2"],
        default="1",
    )
    handler = (
        _handle_query_inspection if sub_choice == "1" else _handle_answer_inspection
    )
    await handler(agent, config)


async def _handle_main_menu_choice(
    choice: int,
    agent: GeminiAgent,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    if choice == 0:
        await run_workflow_interactive(agent, config, logger)
        return
    if choice == 1:
        await _handle_inspection_menu(agent, config)
        return
    if choice == 2:
        await _handle_edit_menu(agent, config)
        return
    if choice == 3:
        show_cache_statistics(config)
        return
    if choice == 4:
        _exit_interactive()
    console.print(f"[red]알 수 없는 선택: {choice}[/red]")


def _confirm_return_to_menu() -> bool:
    console.print("\n[yellow]⚠ 작업을 중단하시겠습니까?[/yellow]")
    if Confirm.ask("메인 메뉴로 돌아가기", default=True):
        console.print("[dim]→ 메인 메뉴로 이동합니다[/dim]\n")
        return True
    _exit_interactive()


def _handle_interactive_exception(exc: Exception, logger: logging.Logger) -> None:
    console.print(f"[red]예기치 않은 오류 발생: {exc}[/red]")
    logger.exception("Interactive menu error")
    Prompt.ask(RETURN_TO_MENU_PROMPT)
