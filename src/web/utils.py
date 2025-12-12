"""공용 웹 API 유틸리티 함수와 상수."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal, TypeAlias, TypedDict, cast

from fastapi import HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

# Type alias to avoid duplicating the literal
_DictStrAny: TypeAlias = dict[str, Any]

# 프로젝트 루트 경로 (templates, data 등 상대 경로 계산에 사용)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Thread-safe OCR cache
_OCR_CACHE: tuple[Path, float, str] | None = None
_OCR_CACHE_LOCK = Lock()

# 질의 유형 매핑 (QA/워크스페이스 공용)
# Phase 2-1: Map globalexplanation to explanation for better rule coverage
QTYPE_MAP = {
    "global_explanation": "explanation",  # Phase 2-1: Use explanation rules
    "globalexplanation": "explanation",  # Phase 2-1: Use explanation rules
    "explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target",
    "target": "target",
    "summary": "summary",
    "factual": "target",
    "general": "explanation",  # Phase 2-1: Use explanation rules
}


def load_ocr_text(config: AppConfig) -> str:
    """data/inputs/input_ocr.txt 로드 (mtime 기반 thread-safe 캐시 포함)."""
    global _OCR_CACHE
    ocr_path: Path = config.input_dir / "input_ocr.txt"
    if not ocr_path.exists():
        raise HTTPException(status_code=404, detail="OCR 파일이 없습니다.")

    mtime = ocr_path.stat().st_mtime

    # Thread-safe cache check and update
    with _OCR_CACHE_LOCK:
        if _OCR_CACHE and _OCR_CACHE[0] == ocr_path and _OCR_CACHE[1] == mtime:
            return _OCR_CACHE[2]

        text = ocr_path.read_text(encoding="utf-8").strip()
        _OCR_CACHE = (ocr_path, mtime, text)
        return text


def save_ocr_text(config: AppConfig, text: str) -> None:
    """OCR 텍스트 저장 (이미지 분석 후) - 캐시 무효화 포함."""
    global _OCR_CACHE
    ocr_path = config.input_dir / "input_ocr.txt"
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    ocr_path.write_text(text, encoding="utf-8")

    # Invalidate cache to ensure next read gets fresh data
    with _OCR_CACHE_LOCK:
        _OCR_CACHE = None


def log_review_session(
    mode: Literal["inspect", "edit"],
    question: str,
    answer_before: str,
    answer_after: str,
    edit_request_used: str,
    inspector_comment: str,
    *,
    base_dir: Path | None = None,
) -> None:
    """검수/수정 세션 로그를 JSONL 파일에 기록."""
    try:
        root = base_dir or REPO_ROOT
        log_dir = root / "data" / "outputs" / "review_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"review_{today}.jsonl"

        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "mode": mode,
            "question": question,
            "answer_before": answer_before,
            "answer_after": answer_after,
            "edit_request_used": edit_request_used,
            "inspector_comment": inspector_comment,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.warning("검수 로그 기록 실패: %s", e)


def strip_output_tags(text: str) -> str:
    """<output> 태그 제거 후 트리밍."""
    return text.replace("<output>", "").replace("</output>", "").strip()


class _StructuredItem(TypedDict, total=False):
    label: str
    text: str


class _StructuredSection(TypedDict, total=False):
    title: str
    items: list[_StructuredItem]
    bullets: list[_StructuredItem]


class _StructuredAnswer(TypedDict, total=False):
    intro: str
    sections: list[_StructuredSection]
    conclusion: str


def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return stripped[start : end + 1]


def _parse_structured_answer(text: str) -> dict[str, Any] | None:
    candidate = _extract_json_object(text)
    if not candidate:
        return None
    if '"intro"' not in candidate and '"sections"' not in candidate:
        return None

    try:
        loaded: Any = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(loaded, dict):
        return None

    # JSON object keys are always strings, but json.loads returns Any.
    return cast(_DictStrAny, loaded)


def _sanitize_structured_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = strip_output_tags(text)
    text = text.replace("**", "")
    text = re.sub(r"(?m)^[ \t]*(?:[-*]|\d+\.)[ \t]+", "", text)
    text = re.sub(r"[\r\n]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ensure_starts_with(
    text: str, prefixes: tuple[str, ...], default_prefix: str
) -> str:
    if not text:
        return text
    if text.startswith(prefixes):
        return text
    return f"{default_prefix}{text}"


def _render_item(item: Any) -> str | None:
    """Render a single item from a section. Returns formatted line or None."""
    if not isinstance(item, dict):
        return None
    item_dict = cast(_DictStrAny, item)
    label = _sanitize_structured_text(item_dict.get("label", ""))
    text = _sanitize_structured_text(item_dict.get("text", ""))
    if label and text:
        return f"- **{label}**: {text}"
    if text:
        return f"- {text}"
    return None


def _ensure_title_spacing(lines: list[str]) -> None:
    """소제목 앞에 적절한 빈줄을 추가."""
    if len(lines) >= 2 and lines[-1] == "" and lines[-2].strip():
        # 이미 빈줄이 있고, 그 앞에 내용이 있으면 한 줄 더 추가
        lines.append("")
    elif lines and lines[-1].strip():
        # 빈줄 없이 내용이 있으면 빈줄 2개 추가 (문단 구분)
        lines.extend(["", ""])


def _render_section(section: Any, lines: list[str]) -> None:
    """Render a single section and append to lines."""
    if not isinstance(section, dict):
        return

    section_dict = cast(_DictStrAny, section)
    title = _sanitize_structured_text(section_dict.get("title", ""))
    items_raw = section_dict.get("items") or section_dict.get("bullets", [])

    if title:
        _ensure_title_spacing(lines)
        lines.append(f"**{title}**")

    if isinstance(items_raw, list):
        for item in items_raw:
            rendered_item = _render_item(item)
            if rendered_item:
                lines.append(rendered_item)

    if lines and lines[-1] != "":
        lines.append("")


def _format_conclusion(conclusion: str, normalized_qtype: str) -> str:
    """Format conclusion with appropriate prefix based on qtype."""
    if normalized_qtype == "explanation":
        return _ensure_starts_with(
            conclusion,
            prefixes=("요약하면", "이처럼"),
            default_prefix="요약하면, ",
        )
    if normalized_qtype == "reasoning":
        return _ensure_starts_with(
            conclusion,
            prefixes=("결론적으로", "따라서", "종합하면", "요약하면"),
            default_prefix="종합하면, ",
        )
    return conclusion


def _render_structured_answer(
    structured: dict[str, Any],
    normalized_qtype: str,
) -> str | None:
    """Render structured JSON answer to markdown format."""
    sections_raw = structured.get("sections", [])
    if not isinstance(sections_raw, list):
        return None

    intro = _sanitize_structured_text(structured.get("intro", ""))
    conclusion = _sanitize_structured_text(structured.get("conclusion", ""))

    lines: list[str] = []
    if intro:
        lines.extend([intro, ""])

    for section in sections_raw:
        _render_section(section, lines)

    conclusion = _format_conclusion(conclusion, normalized_qtype)
    if conclusion:
        lines.append(conclusion)

    rendered = "\n".join(lines).strip()
    return rendered or None


def render_structured_answer_if_present(answer: str, qtype: str) -> str:
    """JSON 구조화 답변이 있으면 마크다운 형태로 렌더링한다.

    - reasoning/explanation 계열에서만 적용
    - 실패 시 원문(answer) 그대로 반환
    """
    normalized = QTYPE_MAP.get(qtype, qtype)
    if normalized not in {"explanation", "reasoning"}:
        return answer

    structured_any = _parse_structured_answer(answer)
    if structured_any is None:
        # JSON 파싱 실패 - 평문 응답으로 추정
        logger.debug(
            "JSON 파싱 실패 (qtype=%s). 원문 샘플: %s...",
            qtype,
            answer[:200] if answer else "(empty)",
        )
        return answer

    rendered = _render_structured_answer(structured_any, normalized)
    if rendered is not None:
        logger.debug("JSON 구조화 답변 렌더링 성공 (qtype=%s)", qtype)
        return rendered
    return answer


def fix_broken_numbers(text: str) -> str:
    r"""잘못 분리된 숫자/소수 표현을 복원한다.

    예:
        "61\n- 7만건" -> "61.7만건"
        "873\n- 3만 건" -> "873.3만 건"
    """
    # 패턴 1: 숫자 + 줄바꿈 + 불릿 + 숫자 → 소수점으로 병합
    text = re.sub(r"(\d)[ \t]*\r?\n-[ \t]*(\d)", r"\1.\2", text)

    # 패턴 2: 연속된 불릿 라인 중 숫자로 시작하는 경우 이전 줄과 병합
    lines = text.splitlines()
    merged: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 2:
            rest = stripped[2:]
            if rest and rest[0].isdigit() and merged:
                merged[-1] = merged[-1].rstrip() + "." + rest
                continue
        merged.append(line)

    return "\n".join(merged)


def detect_workflow(
    query: str | None,
    answer: str | None,
    edit_request: str | None,
) -> Literal[
    "full_generation",
    "edit_both",
    "edit_query",
    "edit_answer",
    "query_generation",
    "answer_generation",
    "rewrite",
]:
    """워크스페이스 모드 감지."""
    has_query = bool(query and query.strip())
    has_answer = bool(answer and answer.strip())
    has_edit = bool(edit_request and edit_request.strip())

    if not has_query and not has_answer:
        return "full_generation"

    if has_query and has_answer:
        return "edit_both" if has_edit else "rewrite"

    if has_query and not has_answer:
        return "edit_query" if has_edit else "answer_generation"

    # has_answer and not has_query: 질문만 생성, 편집 요청 시 답변 수정
    return "edit_answer" if has_edit else "query_generation"


def _limit_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return text


def _normalize_ending_punctuation(text: str) -> str:
    """Replace ellipsis with period, or add period if missing."""
    if not text:
        return text
    if text.endswith("..."):
        return text[:-3] + "."
    if not text.endswith("."):
        return text + "."
    return text


def _ensure_period_preserve_ellipsis(text: str) -> str:
    """Add period if missing, but preserve existing ellipsis."""
    if text and not text.endswith(".") and not text.endswith("..."):
        return text + "."
    return text


def _split_sentences_safe(text: str) -> list[str]:
    """Split sentences carefully, avoiding split on decimal points."""
    protected = re.sub(r"(\d)\.(\d)", r"\1_DOT_\2", text)
    protected = re.sub(r"(\d)\.\s+(\d)", r"\1_DOT_SPACE_\2", protected)
    sentences = [s.strip() for s in protected.split(".") if s.strip()]
    return [s.replace("_DOT_SPACE_", ". ").replace("_DOT_", ".") for s in sentences]


# 실제 사용되는 4가지 질의 타입별 설정 (추후 확장 가능)
_ANSWER_LIMITS_CONFIG: dict[str, dict[str, int]] = {}


def _apply_sentence_word_limits(answer: str, limits: dict[str, int]) -> str:
    sentences = _split_sentences_safe(answer)
    if sentences:
        max_sentences = limits.get("max_sentences", len(sentences))
        sentences = sentences[:max_sentences]
        answer = ". ".join(sentences)
        if answer and not answer.endswith("."):
            answer += "."
    max_words = limits.get("max_words")
    return _limit_words(answer, max_words) if max_words else answer


def _apply_reasoning_limits(answer: str) -> str:
    sentences = _split_sentences_safe(answer)
    if sentences and len(sentences) > 5:
        sentences = sentences[:5]
        answer = ". ".join(sentences)
        if answer and not answer.endswith("."):
            answer += "."
    answer = _limit_words(answer, 200)
    return _normalize_ending_punctuation(answer)


def _truncate_explanation(answer: str, max_length: int | None) -> str:
    if not max_length or len(answer) <= max_length:
        return answer
    truncated = answer[:max_length]
    last_period = truncated.rfind(".")
    if last_period != -1:
        return truncated[: last_period + 1]
    return truncated + "."


def _apply_target_limits(answer: str) -> str:
    word_count = len(answer.split())
    if word_count < 15:
        return _limit_words(answer, 50)

    sentences = _split_sentences_safe(answer)
    if sentences:
        sentences = sentences[:6]
        answer = ". ".join(sentences)
        if answer and not answer.endswith("."):
            answer += "."
    return _limit_words(answer, 200)


def apply_answer_limits(
    answer: str,
    qtype: str,
    max_length: int | None = None,
) -> str:
    """질의 타입별로 답변 길이 제한 적용.

    4가지 실제 질질 타입:
    1. global_explanation: 질질 1 (전체 마모뇌) - 프롬프트로 제어 (1000-1500자)
    2. reasoning: 질질 2 (추론) - 프롬프트로 제어 (제약 없음, 답변 손실 방지)
    3. target (short): 질질 3 (숫자/명칭) - 단답형 자동 탐지
    4. target (long): 질질 4 (강조) - 서술형 자동 탐지
    """
    # Normalize qtype locally
    normalized_qtype = QTYPE_MAP.get(qtype, qtype)

    if normalized_qtype in _ANSWER_LIMITS_CONFIG:
        return _apply_sentence_word_limits(
            answer,
            _ANSWER_LIMITS_CONFIG[normalized_qtype],
        )

    if normalized_qtype == "reasoning":
        return _apply_reasoning_limits(answer)

    if normalized_qtype == "explanation":
        answer = _ensure_period_preserve_ellipsis(answer)
        return _truncate_explanation(answer, max_length)

    if normalized_qtype == "target":
        return _apply_target_limits(answer)

    return answer


def _strip_code_and_links(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\|.*\|\s*$", " ", text, flags=re.MULTILINE)  # table rows
    return text


def _remove_unauthorized_markdown(text: str) -> str:
    """허용되지 않은 마크다운만 선별적으로 제거.

    전략:
    1. ### 헤더 제거 (샵 기호만 제거하여 평문으로 변환)
    2. *italic* 제거하되 **bold**는 보호
       - **bold**를 고유한 임시 토큰으로 변환
       - 홑별표(*) 제거
       - 임시 토큰을 **bold**로 복원
    """
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    bold_placeholder = "##BOLD_PLACEHOLDER_8A3F2E1C##"
    text = text.replace("**", bold_placeholder)
    text = re.sub(r"\*([^*]+?)\*", r"\1", text)
    text = text.replace("*", "")
    return text.replace(bold_placeholder, "**")


def _is_existing_markdown_line(stripped: str) -> bool:
    return stripped.startswith("**") or stripped.startswith("- **")


def _convert_dash_bullet(line: str) -> str:
    stripped = line.strip()
    bullet_content = stripped[2:].strip()
    if ": " in bullet_content and not bullet_content.startswith("**"):
        item_name, item_desc = bullet_content.split(": ", 1)
        return f"- **{item_name}**: {item_desc}"
    return line


def _is_section_header_line(stripped: str, next_stripped: str) -> bool:
    if not next_stripped:
        return False
    return (
        ": " in next_stripped
        and not next_stripped.startswith("-")
        and len(stripped) <= 50
        and ": " not in stripped
    )


def _convert_colon_item_line(stripped: str) -> str | None:
    if ": " not in stripped:
        return None
    potential_name, item_desc = stripped.split(": ", 1)
    if len(potential_name) <= 30 and "." not in potential_name:
        return f"- **{potential_name}**: {item_desc}"
    return None


def _add_markdown_structure(text: str, qtype: str) -> str:
    """평문에 마크다운 구조 자동 추가.

    패턴 분석:
    1. 소제목: 단독 줄 + 다음 줄에 '항목명:' 패턴 → **굵은 소제목**
    2. 불릿 항목: '항목명: 설명' 패턴 → - **항목명**: 설명

    target 타입은 평문 유지 (마크다운 추가하지 않음).
    """
    normalized = QTYPE_MAP.get(qtype, qtype)
    if normalized != "explanation":
        return text

    lines = text.split("\n")
    result: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or _is_existing_markdown_line(stripped):
            result.append(line)
            continue

        if stripped.startswith("- "):
            result.append(_convert_dash_bullet(line))
            continue

        next_stripped = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
        if _is_section_header_line(stripped, next_stripped):
            result.append(f"**{stripped}**")
            continue

        colon_item = _convert_colon_item_line(stripped)
        if colon_item is not None:
            result.append(colon_item)
            continue

        result.append(line)

    return "\n".join(result)


def postprocess_answer(
    answer: str,
    qtype: str,
    max_length: int | None = None,
) -> str:
    """답변 후처리 - CSV 규칙에 맞게 마크다운 정리.

    CSV 규칙 (guide.csv, qna.csv)에서 허용하는 마크다운:
    - ✅ **bold**: 핵심 키워드 강조
    - ✅ 1. 2. 3.: 순서가 있는 목록
    - ✅ - 항목: 순서가 없는 불릿 목록

    허용되지 않은 마크다운 (제거 대상):
    - ❌ *italic*: 가독성 저하
    - ❌ ### 제목: 불필요한 헤더
    """
    # 1. 태그 제거
    answer = strip_output_tags(answer)
    answer = render_structured_answer_if_present(answer, qtype)
    answer = _strip_code_and_links(answer)

    # 2. 숫자 포맷 깨짐 복원
    answer = fix_broken_numbers(answer)

    # 3. 허용되지 않은 마크다운 제거 (CSV 규칙 준수)
    answer = _remove_unauthorized_markdown(answer)

    # 3.5. 서론-소제목 붙음 분리 (예: "문장입니다. **제목**" → 줄바꿈 추가)
    # 패턴: 문장 끝(다/요/음/임 등 + .) 뒤에 **로 시작하는 소제목이 바로 오는 경우
    answer = re.sub(
        r"([.?!])(\s*)(\*\*[^*]+\*\*)",
        r"\1\n\n\3",
        answer,
    )

    # 4. 기본 정리
    answer = answer.strip()

    # 5. 불필요한 줄바꿈 정리 (마크다운 유지하면서)
    # 연속된 빈 줄은 최대 2개까지만 유지 (= 최대 3개의 \n 문자)
    # 단, 불릿 사이의 빈줄은 제거 (동일 범주는 줄바꿈 없이)
    lines = answer.split("\n")
    cleaned_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 현재 줄이 빈줄인 경우
        if stripped == "":
            # 다음 유효 줄 찾기
            next_content_idx = None
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    next_content_idx = j
                    break

            # 이전 줄이 불릿이고 다음 줄도 불릿이면 빈줄 제거
            if cleaned_lines:
                prev_stripped = cleaned_lines[-1].strip()
                prev_is_bullet = prev_stripped.startswith("- ")
                next_is_bullet = next_content_idx is not None and lines[
                    next_content_idx
                ].strip().startswith("- ")
                if prev_is_bullet and next_is_bullet:
                    continue  # 불릿 사이 빈줄 건너뛰기

            # 연속 빈줄 최대 2개
            empty_count = sum(1 for ln in reversed(cleaned_lines) if not ln.strip())
            if empty_count < 2:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    answer = "\n".join(cleaned_lines)

    # 6. 마크다운 구조 자동 추가 (소제목, 불릿 항목에 볼드)
    answer = _add_markdown_structure(answer, qtype)

    # 7. 길이 제한 적용
    answer = apply_answer_limits(answer, qtype, max_length=max_length)

    return answer.strip()


__all__ = [
    "QTYPE_MAP",
    "REPO_ROOT",
    "apply_answer_limits",
    "detect_workflow",
    "fix_broken_numbers",
    "load_ocr_text",
    "log_review_session",
    "postprocess_answer",
    "render_structured_answer_if_present",
    "save_ocr_text",
    "strip_output_tags",
]
