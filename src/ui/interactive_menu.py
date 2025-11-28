"""Interactive Menu UI for Gemini Workflow System."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.caching.analytics import analyze_cache_stats, print_cache_report
from src.caching.redis_cache import RedisEvalCache
from src.config import AppConfig
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


def show_error_with_guide(error_type: str, message: str, solution: str) -> None:
    """에러 메시지 + 해결 방법 표시"""
    console.print(f"\n[red]✗ {error_type}: {message}[/red]")
    console.print(f"[dim]💡 해결 방법: {solution}[/dim]\n")


def show_main_menu() -> int:
    """메인 메뉴 - 기능 플래그 상태 표시 포함"""
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
    agent: GeminiAgent, config: AppConfig, logger: logging.Logger
) -> None:
    """질의 생성 및 평가 - 에러 핸들링 강화"""

    # 1. API 키 검증
    if not config.api_key or not config.api_key.startswith("AIza"):
        show_error_with_guide(
            "API 키가 유효하지 않습니다",
            "GEMINI_API_KEY가 설정되지 않았거나 형식이 올바르지 않습니다",
            ".env 파일에서 GEMINI_API_KEY='AIza...'로 시작하는 키를 설정하세요",
        )
        Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")
        return

    # 2. 파일 존재 확인
    ocr_file = Prompt.ask("OCR 파일명", default="input_ocr.txt")
    cand_file = Prompt.ask("후보 답변 파일명", default="input_candidates.json")

    ocr_path = config.input_dir / ocr_file
    cand_path = config.input_dir / cand_file

    if not ocr_path.exists():
        console.print(f"[red]✗ OCR 파일이 없습니다: {ocr_path}[/red]")
        if Confirm.ask("빈 파일을 생성할까요?", default=True):
            ocr_path.parent.mkdir(parents=True, exist_ok=True)
            ocr_path.write_text("", encoding="utf-8")
            console.print("[green]✓ 파일 생성됨 - IDE에서 내용을 입력하세요[/green]")
        else:
            return

    if not cand_path.exists():
        console.print(f"[red]✗ 후보 답변 파일이 없습니다: {cand_path}[/red]")
        if Confirm.ask("템플릿을 생성할까요?", default=True):
            import json

            template = {"a": "첫 번째 답변", "b": "두 번째 답변", "c": "세 번째 답변"}
            cand_path.parent.mkdir(parents=True, exist_ok=True)
            cand_path.write_text(
                json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            console.print("[green]✓ 템플릿 생성됨 - IDE에서 답변을 입력하세요[/green]")
        else:
            return

    # 3. 데이터 로드
    try:
        ocr_text, candidates = await load_input_data(
            config.input_dir, ocr_file, cand_file
        )
    except FileNotFoundError as e:
        show_error_with_guide(
            "파일을 찾을 수 없습니다",
            str(e),
            "IDE에서 data/inputs/ 폴더에 파일을 생성하세요",
        )
        Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")
        return
    except Exception as e:
        import json

        if isinstance(e.__cause__, json.JSONDecodeError):
            show_error_with_guide(
                "JSON 파싱 오류",
                "후보 답변 파일 형식이 올바르지 않습니다",
                '올바른 형식: {"a": "답변1", "b": "답변2", "c": "답변3"}',
            )
        else:
            show_error_with_guide(
                "데이터 로드 실패",
                str(e),
                "파일 경로와 형식을 확인하세요",
            )
        Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")
        return

    # 4. 사용자 의도 입력
    user_intent = Prompt.ask("사용자 의도 (선택)", default="")

    # 5. 질의 생성 (진행 표시 개선)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("전략적 질의 생성 중...", total=None)
        try:
            queries = await agent.generate_query(ocr_text, user_intent or None)
            progress.update(task, description="[green]✓ 질의 생성 완료[/green]")
        except Exception as e:
            progress.update(task, description="[red]✗ 질의 생성 실패[/red]")
            show_error_with_guide(
                "질의 생성 실패",
                str(e),
                "API 키와 네트워크 연결을 확인하고 다시 시도하세요",
            )
            Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")
            return

    if not queries:
        console.print("[yellow]생성된 질의가 없습니다.[/yellow]")
        return

    display_queries(queries)

    if not Confirm.ask("위 질의들로 진행하시겠습니까?", default=True):
        console.print("[yellow]작업이 취소되었습니다.[/yellow]")
        return

    # 6. 질의 처리 (결과 추적)
    console.print(f"\n[bold]⚙️  {len(queries)}개 질의 처리 시작[/bold]\n")

    results: List[Optional[WorkflowResult]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for i, query in enumerate(queries):
            turn_id = i + 1
            task = progress.add_task(
                f"[cyan]질의 {turn_id}/{len(queries)}: {query[:50]}...[/cyan]",
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

                if result and result.success:
                    progress.update(
                        task,
                        description=f"[green]✓ 질의 {turn_id}/{len(queries)} 완료[/green]",
                    )
                else:
                    progress.update(
                        task,
                        description=f"[yellow]⚠ 질의 {turn_id}/{len(queries)} 건너뜀[/yellow]",
                    )
            except Exception:
                logger.exception(f"Query {turn_id} failed")
                progress.update(
                    task,
                    description=f"[red]✗ 질의 {turn_id}/{len(queries)} 실패[/red]",
                )
                results.append(None)

    # 결과 요약 표시
    _display_workflow_summary(queries, results, agent, config, timestamp)

    Prompt.ask("\n엔터를 눌러 메뉴로 돌아갑니다")


async def _handle_query_inspection(agent: GeminiAgent, config: AppConfig) -> None:
    """
    질의 검수 핸들러 (Direct Input -> CLI Output)

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
    cache: Optional[RedisEvalCache] = None
    if os.getenv("REDIS_URL"):
        cache = RedisEvalCache()

    try:
        # [3] 실행 & 출력
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]최적화 중...", total=None)

            # Context 구성
            context = {"type": "general"}

            fixed_query = await inspect_query(
                agent, query_input, ocr_text, context, kg, lats, difficulty, cache
            )

            progress.update(task, completed=100, description="[green]✓ 완료[/green]")

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
    """
    답변 검수 핸들러 (File Input -> File Output)

    UX 원칙:
    - 파일 경로 입력 (긴 텍스트)
    - OCR 자동 로드 (사실 검증용)
    - 결과 파일 저장 (CLI 출력 없음)
    """
    console.print(Panel("✅ 답변 검수 모드", style="cyan"))

    # [1] 파일 입력
    answer_file_str = Prompt.ask("\n📂 답변 파일 경로")
    answer_file = Path(answer_file_str.strip())

    if not answer_file.exists():
        console.print(f"[red]파일이 존재하지 않습니다: {answer_file}[/red]")
        return

    answer = answer_file.read_text(encoding="utf-8")
    if not answer.strip():
        console.print("[yellow]답변 파일이 비어있습니다.[/yellow]")
        return

    # [2] OCR 자동 로드 (사실 검증용)
    ocr_text = ""
    ocr_file = Path(DEFAULT_OCR_PATH)
    if ocr_file.exists():
        console.print(f"[dim]📄 OCR 자동 로드: {ocr_file}[/dim]")
        ocr_text = ocr_file.read_text(encoding="utf-8")
    else:
        # OCR 파일이 없으면 사용자에게 경로 입력 요청
        ocr_path_input = Prompt.ask("OCR 파일 경로", default="")
        if ocr_path_input:
            ocr_path = Path(ocr_path_input.strip())
            if ocr_path.exists():
                ocr_text = ocr_path.read_text(encoding="utf-8")
            else:
                console.print(
                    f"[yellow]OCR 파일을 찾을 수 없습니다: {ocr_path}[/yellow]"
                )

    # [3] 질의 여부 (선택)
    query = ""
    if Prompt.ask("❓ 질의 입력?", choices=["y", "n"], default="n").lower() == "y":
        query = Prompt.ask("   질의")

    # 리소스 초기화
    kg = QAKnowledgeGraph() if config.neo4j_uri else None
    lats = LATSSearcher(agent.llm_provider) if config.enable_lats else None
    validator = CrossValidationSystem(kg) if kg else None
    cache: Optional[RedisEvalCache] = None
    if os.getenv("REDIS_URL"):
        cache = RedisEvalCache()

    try:
        # [4] 실행 & 저장 (CLI 출력 X)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/outputs")
        output_path = output_dir / f"inspected_{timestamp}.md"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]검수 및 수정 중...", total=None)

            context = {"type": "general", "image_meta": {}}

            fixed_answer = await inspect_answer(
                agent, answer, query, ocr_text, context, kg, lats, validator, cache
            )

            # 결과 저장
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(fixed_answer, encoding="utf-8")

            progress.update(task, completed=100, description="[green]✓ 완료[/green]")

        console.print("\n✅ [bold green]완료[/bold green]")
        console.print(f"💾 저장됨: {output_path}")

    except Exception as e:
        console.print(f"[red]검수 실패: {e}[/red]")
    finally:
        if kg:
            kg.close()


async def _handle_edit_menu(agent: GeminiAgent, config: AppConfig) -> None:
    """
    수정 메뉴 핸들러 (사용자 요청 기반 재작성)

    UX 원칙:
    - 답변 파일 입력
    - OCR 자동 로드
    - 질의 선택 입력
    - 간결한 수정 요청 한 줄 입력
    - 결과 파일 저장 (CLI 출력 없음)
    """
    console.print(Panel("✏️ 수정 모드: 간결한 요청으로 내용 재작성", style="cyan"))

    # [1] 답변 파일 입력
    answer_file_str = Prompt.ask("\n📂 수정할 답변 파일 경로")
    answer_file = Path(answer_file_str.strip())

    if not answer_file.exists():
        console.print(f"[red]❌ 파일을 찾을 수 없습니다: {answer_file}[/red]")
        return

    answer_text = answer_file.read_text(encoding="utf-8")
    if not answer_text.strip():
        console.print("[yellow]답변 파일이 비어있습니다.[/yellow]")
        return

    # [2] OCR 자동 로드
    ocr_text = ""
    ocr_file = Path(DEFAULT_OCR_PATH)
    if ocr_file.exists():
        console.print(f"[dim]📄 OCR 자동 로드: {ocr_file}[/dim]")
        ocr_text = ocr_file.read_text(encoding="utf-8")
    else:
        # OCR 파일이 없으면 사용자에게 경로 입력 요청 (한 번만)
        ocr_path_input = Prompt.ask("📄 OCR 파일 경로 (없으면 Enter)", default="")
        if ocr_path_input:
            ocr_path = Path(ocr_path_input.strip())
            if ocr_path.exists():
                ocr_text = ocr_path.read_text(encoding="utf-8")
            else:
                console.print(
                    f"[yellow]OCR 파일을 찾을 수 없습니다: {ocr_path}[/yellow]"
                )
        if not ocr_text:
            console.print("[dim]⚠ OCR 텍스트 없음 (컨텍스트 없이 수정합니다)[/dim]")

    # [3] 질의 입력 (선택)
    query = ""
    if Prompt.ask("❓ 질의를 문맥에 포함할까요?", choices=["y", "n"], default="n").lower() == "y":
        query = Prompt.ask("   ❓ 질의 내용")

    # [4] 수정 요청 입력 (핵심)
    edit_request = Prompt.ask("\n✏️ 어떻게 수정할까요? (한 줄)")
    if not edit_request.strip():
        console.print("[red]❌ 수정 요청이 없습니다.[/red]")
        return

    # 리소스 초기화
    kg = QAKnowledgeGraph() if config.neo4j_uri else None
    cache: Optional[RedisEvalCache] = None
    if os.getenv("REDIS_URL"):
        cache = RedisEvalCache()

    try:
        # [5] 수정 실행
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/outputs")
        output_path = output_dir / f"edited_{timestamp}.md"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
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
                cache=cache,
            )

            # 결과 저장
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(edited_text, encoding="utf-8")

            progress.update(task, completed=100, description="[green]✓ 완료[/green]")

        console.print("\n✅ [bold green]수정 완료[/bold green]")
        console.print(f"💾 저장됨: {output_path}")

    except Exception as e:
        console.print(f"[red]❌ 수정 중 오류 발생: {e}[/red]")
    finally:
        if kg:
            kg.close()


def show_cache_statistics(config: AppConfig) -> None:
    """캐시 통계 분석"""
    console.print("\n[bold]캐시 통계 분석[/bold]")
    try:
        summary = analyze_cache_stats(config.cache_stats_path)
        print_cache_report(summary)
    except Exception as e:
        console.print(f"[red]통계 분석 실패: {e}[/red]")
    Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")


def _display_workflow_summary(
    queries: List[str],
    results: List[Optional[WorkflowResult]],
    agent: GeminiAgent,
    config: AppConfig,
    timestamp: str,
) -> None:
    """워크플로우 완료 후 결과 요약 표시"""
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
            status = "[green]✓ 완료[/green]"
            success_count += 1
        else:
            output_file = "-"
            status = "[red]✗ 실패[/red]"

        # 질의 텍스트 잘라내기
        query_display = query[:47] + "..." if len(query) > 50 else query
        table.add_row(str(i), query_display, status, output_file)

    console.print(table)

    # 통계 정보
    console.print(f"\n[bold]성공: {success_count}/{len(queries)}[/bold]")

    # 비용/토큰 정보 (Budget Panel 통합)
    console.print()
    console.print(render_budget_panel(agent))
    console.print(render_cost_panel(agent))


async def interactive_main(
    agent: GeminiAgent, config: AppConfig, logger: logging.Logger
) -> None:
    """대화형 메인 루프"""
    while True:
        try:
            choice = show_main_menu()

            if choice == 0:  # 1. 질의 생성 및 평가
                await run_workflow_interactive(agent, config, logger)
            elif choice == 1:  # 2. 검수
                # Sub-menu for review? Or just separate options?
                # The menu has "2. 검수 (질의/답변)"
                # Let's ask which one.
                sub_choice = Prompt.ask(
                    "검수 유형 선택 (1: 질의, 2: 답변)", choices=["1", "2"], default="1"
                )
                if sub_choice == "1":
                    await _handle_query_inspection(agent, config)
                else:
                    await _handle_answer_inspection(agent, config)
            elif choice == 2:  # 3. 수정
                await _handle_edit_menu(agent, config)
            elif choice == 3:  # 4. 캐시 통계
                show_cache_statistics(config)
            elif choice == 4:  # 5. 종료
                console.print("[bold]시스템을 종료합니다. 안녕히 가세요! 👋[/bold]")
                sys.exit(0)
        except KeyboardInterrupt:  # noqa: PERF203 - Required for graceful error recovery in UI loop
            console.print("\n[yellow]⚠ 작업을 중단하시겠습니까?[/yellow]")
            if Confirm.ask("메인 메뉴로 돌아가기", default=True):
                console.print("[dim]→ 메인 메뉴로 이동합니다[/dim]\n")
                continue  # 메인 메뉴로 돌아가기
            else:
                console.print("[bold]시스템을 종료합니다. 안녕히 가세요! 👋[/bold]")
                sys.exit(0)
        except Exception as e:
            console.print(f"[red]예기치 않은 오류 발생: {e}[/red]")
            logger.exception("Interactive menu error")
            Prompt.ask("엔터를 눌러 메뉴로 돌아갑니다")
