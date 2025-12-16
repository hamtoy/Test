"""공용 웹 API 유틸리티 함수와 상수."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypedDict, cast

import aiofiles
from fastapi import HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

# Type alias to avoid duplicating the literal
_DictStrAny: TypeAlias = dict[str, Any]

# 프로젝트 루트 경로 (templates, data 등 상대 경로 계산에 사용)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Thread-safe OCR cache
_OCR_CACHE: tuple[Path, float, str] | None = None
_OCR_CACHE_LOCK = asyncio.Lock()

# 질의 유형 매핑 (QA/워크스페이스 공용)
# Phase 2-1: Map globalexplanation to explanation for better rule coverage
QTYPE_MAP = {
    "global_explanation": "explanation",  # Phase 2-1: Use explanation rules
    "globalexplanation": "explanation",  # Phase 2-1: Use explanation rules
    "explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target_long",
    "target": "target",
    "summary": "summary",
    "factual": "target",
    "general": "explanation",  # Phase 2-1: Use explanation rules
}


async def load_ocr_text(config: AppConfig) -> str:
    """data/inputs/input_ocr.txt 로드 (mtime 기반 thread-safe 캐시 포함)."""
    global _OCR_CACHE
    ocr_path: Path = config.input_dir / "input_ocr.txt"
    if not ocr_path.exists():
        raise HTTPException(status_code=404, detail="OCR 파일이 없습니다.")

    mtime = ocr_path.stat().st_mtime

    # Thread-safe cache check and update
    async with _OCR_CACHE_LOCK:
        if _OCR_CACHE and _OCR_CACHE[0] == ocr_path and _OCR_CACHE[1] == mtime:
            return _OCR_CACHE[2]

        async with aiofiles.open(ocr_path, encoding="utf-8") as f:
            text = (await f.read()).strip()
        _OCR_CACHE = (ocr_path, mtime, text)
        return text


async def save_ocr_text(config: AppConfig, text: str) -> None:
    """OCR 텍스트 저장 (이미지 분석 후) - 캐시 무효화 포함."""
    global _OCR_CACHE
    ocr_path = config.input_dir / "input_ocr.txt"
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(ocr_path, "w", encoding="utf-8") as f:
        await f.write(text)

    # Invalidate cache to ensure next read gets fresh data
    async with _OCR_CACHE_LOCK:
        _OCR_CACHE = None


async def log_review_session(
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

        async with aiofiles.open(log_file, "a", encoding="utf-8") as f:
            await f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

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
        logger.debug("JSON 추출 실패: { } 를 찾을 수 없음")
        return None

    # LLM이 JSON 키에 **를 적용하는 경우 제거 (예: **"intro"** → "intro")
    candidate = candidate.replace('**"', '"').replace('"**', '"')
    candidate = candidate.replace("**'", "'").replace("'**", "'")
    # 단독 **도 제거
    candidate = candidate.replace("**", "")

    # LLM이 마크다운 리스트 마커를 추가하는 경우 제거 (예: - "intro" → "intro")
    # 각 줄에서 `- ` 프리픽스 제거
    lines = candidate.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("- "):
            # `- ` 제거하고 원래 들여쓰기 유지
            indent = line[: len(line) - len(stripped)]
            cleaned_lines.append(indent + stripped[2:])
        else:
            cleaned_lines.append(line)
    candidate = "\n".join(cleaned_lines)

    if '"intro"' not in candidate and '"sections"' not in candidate:
        logger.debug(
            "JSON 키 조건 불충족: intro/sections 없음. 샘플: %s", candidate[:300]
        )
        return None

    try:
        loaded: Any = json.loads(candidate)
        logger.debug(
            "JSON 파싱 성공: keys=%s",
            list(loaded.keys()) if isinstance(loaded, dict) else type(loaded),
        )
    except json.JSONDecodeError as e:
        logger.warning("JSON 파싱 오류: %s. 샘플: %s", e, candidate[:300])
        return None

    if not isinstance(loaded, dict):
        logger.debug("JSON이 dict가 아님: %s", type(loaded))
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


def _split_conclusion_block(
    answer: str,
    normalized_qtype: str,
) -> tuple[str, str] | None:
    """본문/결론을 분리한다.

    - 우선: 렌더러가 추가한 '**결론**' 섹션 기준으로 분리
    - 보조: 마지막 줄이 결론 접두어로 시작하면 결론으로 간주
    """
    lines = answer.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip() == "**결론**":
            prefix = "\n".join(lines[:idx]).rstrip()
            conclusion = "\n".join(lines[idx:]).strip()
            return prefix, conclusion

    prefixes: tuple[str, ...]
    if normalized_qtype == "explanation":
        prefixes = ("요약하면", "이처럼")
    elif normalized_qtype == "reasoning":
        prefixes = ("결론적으로", "따라서", "종합하면", "요약하면")
    else:
        prefixes = ()

    for idx in range(len(lines) - 1, -1, -1):
        candidate = lines[idx].strip()
        if not candidate:
            continue
        if prefixes and candidate.startswith(prefixes):
            prefix = "\n".join(lines[:idx]).rstrip()
            return prefix, candidate
        break

    return None


def _truncate_markdown_preserving_lines(text: str, max_length: int) -> str:
    """마크다운 라인 단위로 최대 길이까지 잘라낸다."""
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text.rstrip()

    lines = text.splitlines()
    kept: list[str] = []
    current_len = 0
    for line in lines:
        add_len = len(line) + (1 if kept else 0)  # join 시 '\n'
        if current_len + add_len > max_length:
            break
        kept.append(line)
        current_len += add_len

    if kept:
        return "\n".join(kept).rstrip()

    truncated = text[:max_length]
    last_period = truncated.rfind(".")
    if last_period != -1:
        return truncated[: last_period + 1].rstrip()
    return truncated.rstrip()


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
    if not conclusion:
        conclusion = _get_fallback_conclusion(intro, normalized_qtype)

    lines: list[str] = []
    if intro:
        lines.extend([intro, ""])

    for section in sections_raw:
        _render_section(section, lines)

    conclusion = _format_conclusion(conclusion, normalized_qtype)
    if conclusion:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(conclusion)

    rendered = "\n".join(lines).strip()
    return rendered or None


def _get_fallback_conclusion(intro: str, normalized_qtype: str) -> str:
    """결론이 없을 때 폴백 결론 생성."""
    if normalized_qtype == "reasoning":
        # 추론 유형: 첫 문장 기반으로 결론 생성
        if intro:
            sentences = _split_sentences_safe(intro)
            if sentences:
                first_sentence = sentences[0].strip()
                # 이미 결론 접두어로 시작하면 그대로 반환
                if first_sentence.startswith(("결론적으로", "따라서", "종합하면")):
                    return first_sentence
                return f"결론적으로, {first_sentence}"
        return "결론적으로, 위 근거를 바탕으로 같은 판단입니다."

    if normalized_qtype == "explanation":
        if intro:
            sentences = _split_sentences_safe(intro)
            if sentences:
                return f"요약하면, {sentences[0].strip()}"
        return "요약하면, 핵심 내용은 위와 같습니다."

    return ""


def render_structured_answer_if_present(answer: str, qtype: str) -> str:
    """JSON 구조화 답변이 있으면 마크다운 형태로 렌더링한다.

    - reasoning/explanation/target 계열에서 적용
    - 실패 시 원문(answer) 그대로 반환
    """
    normalized = QTYPE_MAP.get(qtype, qtype)
    if normalized not in {"explanation", "reasoning", "target"}:
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

    # target은 intro만 출력 (짧은 단답형)
    if normalized == "target":
        intro = _sanitize_structured_text(structured_any.get("intro", ""))
        return intro if intro else answer

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
    """추론형: 결론 필수, 포맷 보존."""
    # 본문/결론 분리
    split_result = _split_conclusion_block(answer, "reasoning")
    if split_result is None:
        body, conclusion = answer, ""
    else:
        body, conclusion = split_result

    # 결론이 없거나 너무 짧으면 폴백 추가
    if not conclusion or len(conclusion.strip()) < 20:
        conclusion = _get_fallback_conclusion(body, "reasoning")

    # 결론 앞 빈줄 보장
    if conclusion and body and not body.rstrip().endswith("\n\n"):
        body = body.rstrip() + "\n\n"

    result = (body + conclusion).strip()

    # 기존 길이 제한 로직
    sentences = _split_sentences_safe(result)
    if sentences and len(sentences) > 5:
        sentences = sentences[:5]
        result = ". ".join(sentences)
        if result and not result.endswith("."):
            result += "."
    result = _limit_words(result, 200)
    return _normalize_ending_punctuation(result)


def _truncate_explanation(answer: str, max_length: int | None) -> str:
    if not max_length or len(answer) <= max_length:
        return answer

    split = _split_conclusion_block(answer, normalized_qtype="explanation")
    if split is None:
        truncated = answer[:max_length]
        last_period = truncated.rfind(".")
        if last_period != -1:
            return truncated[: last_period + 1]
        return truncated + "."

    prefix, conclusion_block = split
    separator = "\n\n"

    if len(conclusion_block) >= max_length:
        truncated = answer[:max_length]
        last_period = truncated.rfind(".")
        if last_period != -1:
            return truncated[: last_period + 1]
        return truncated + "."

    budget = max_length - len(conclusion_block) - len(separator)
    if budget <= 0:
        return conclusion_block[:max_length].rstrip()

    truncated_prefix = _truncate_markdown_preserving_lines(prefix, budget)
    if truncated_prefix:
        return f"{truncated_prefix}{separator}{conclusion_block}".strip()
    return conclusion_block.strip()


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


def _apply_target_long_limits(answer: str) -> str:
    """타겟 장답형: 200-400자, 3-4문장.

    타겟 단답(1-2문장)보다 길게 유지하여 구분을 명확히 함.
    """
    sentences = _split_sentences_safe(answer)
    if not sentences:
        return answer

    # 3-4문장 유지 (단답은 1-2문장)
    if len(sentences) > 4:
        sentences = sentences[:4]

    result = ". ".join(sentences)
    if result and not result.endswith("."):
        result += "."

    # 200-400자 목표 (단답보다 길게)
    if len(result) > 400:
        # 400자 넘으면 마지막 문장 잘라서 맞춤
        truncated = result[:397]
        last_period = truncated.rfind(".")
        result = (
            truncated[: last_period + 1] if last_period > 200 else truncated + "..."
        )

    return result


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

    if normalized_qtype == "target_long":
        return _apply_target_long_limits(answer)

    if normalized_qtype == "target":  # target_short만 해당
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


def strip_prose_bold(text: str) -> str:
    """줄글 본문 내 볼드체를 강제 제거한다.

    prose_bold_violation 교정용: 목록/소제목 컨텍스트가 아닌 곳의 볼드체만 제거.

    허용되는 볼드체 (유지):
    - 목록 항목 시작: "- **항목**: 설명"
    - 숫자 목록: "1. **항목**: 설명"
    - 단독 소제목: "**제목**" (줄 전체가 볼드)

    제거 대상:
    - 줄글 내 볼드: "이것은 **강조** 단어입니다" → "이것은 강조 단어입니다"
    """
    lines = text.split("\n")
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # 허용 패턴 1: 목록 항목 시작 (- ** 또는 숫자. **)
        if re.match(r"^-\s+\*\*", stripped) or re.match(r"^\d+\.\s+\*\*", stripped):
            result_lines.append(line)
            continue

        # 허용 패턴 2: 줄 전체가 볼드 소제목
        if re.match(r"^\*\*[^*]+\*\*\s*$", stripped):
            result_lines.append(line)
            continue

        # 그 외: 줄글 내 볼드체 모두 제거
        cleaned_line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        result_lines.append(cleaned_line)

    return "\n".join(result_lines)


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


def _normalize_blank_lines(text: str) -> str:
    """불릿 사이 빈줄 제거 및 연속 빈줄 최대 2개로 제한."""
    lines = text.split("\n")
    cleaned_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "":
            # 다음 유효 줄 찾기
            next_content_idx = _find_next_content_line(lines, i)

            # 이전 줄이 불릿이고 다음 줄도 불릿이면 빈줄 제거
            if cleaned_lines and _is_between_bullets(
                cleaned_lines, lines, next_content_idx
            ):
                continue

            # 연속 빈줄 최대 2개
            empty_count = sum(1 for ln in reversed(cleaned_lines) if not ln.strip())
            if empty_count < 2:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _find_next_content_line(lines: list[str], start: int) -> int | None:
    """다음 비어있지 않은 줄의 인덱스를 찾음."""
    for j in range(start + 1, len(lines)):
        if lines[j].strip():
            return j
    return None


def _is_between_bullets(
    cleaned_lines: list[str], lines: list[str], next_idx: int | None
) -> bool:
    """이전 줄과 다음 줄이 모두 불릿인지 확인."""
    prev_stripped = cleaned_lines[-1].strip()
    prev_is_bullet = prev_stripped.startswith("- ")
    next_is_bullet = next_idx is not None and lines[next_idx].strip().startswith("- ")
    return prev_is_bullet and next_is_bullet


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
    # 패턴: 한글 종결어미 뒤 (마침표 있든 없든) **로 시작하는 소제목이 오는 경우
    answer = re.sub(
        r"(다|요|음|임|됨|함|습니다|입니다|였습니다|됩니다|합니다|겠습니다)(\.?)(\s*)(\*\*[^*]+\*\*)",
        r"\1\2\n\n\4",
        answer,
    )

    # 3.5.1. 마침표/물음표/느낌표 뒤 소제목 분리 (위에서 못 잡은 경우)
    answer = re.sub(
        r"([.?!])(\s*)(\*\*[^*]+\*\*)",
        r"\1\n\n\3",
        answer,
    )

    # 3.5.2. 줄 시작이 소제목인데 바로 앞 줄이 빈줄이 아니면 빈줄 추가
    answer = re.sub(
        r"([^\n])\n(\*\*[^*]+\*\*)",
        r"\1\n\n\2",
        answer,
    )

    # 3.6. 서론/본론/결론 같은 구조 라벨 제거
    # 다양한 형태 처리: **서론**, *서론*, 서론:, (서론), [서론] 등
    label_patterns = [
        r"^\*{1,3}\s*(서론|본론|결론|도입|마무리)\s*\*{1,3}\s*$",  # *서론*, **서론**, ***서론***
        r"^(서론|본론|결론|도입|마무리)\s*[:：]\s*$",  # 서론:, 본론:
        r"^[\[\(]\s*(서론|본론|결론|도입|마무리)\s*[\]\)]\s*$",  # [서론], (본론)
    ]
    for pattern in label_patterns:
        answer = re.sub(pattern, "", answer, flags=re.MULTILINE)

    # 3.6.1. 불필요한 단독 소제목 제거 (투자의견 유지, 목표주가 유지 등)
    # 내용 없이 소제목만 있는 줄 제거
    answer = re.sub(
        r"^\*\*(투자의견|목표주가|투자등급).*?\*\*\s*$",
        "",
        answer,
        flags=re.MULTILINE,
    )

    # 3.7. 결론 접두어 앞에 빈 줄 추가 (본론과 결론 분리)
    # 패턴: 결론 접두어(요약하면, 종합하면, 결론적으로)가 바로 이전 내용에 붙어있는 경우
    answer = re.sub(
        r"([.?!다요음임])\s*(요약하면|종합하면|결론적으로|정리하면)",
        r"\1\n\n\2",
        answer,
    )

    # 3.7.1. 결론 접두어 중복 제거 (요약하면, 종합하면 등이 연속으로 나오면 첫 번째만 유지)
    answer = re.sub(
        r"(요약하면|종합하면|결론적으로|정리하면)[,\s]*(요약하면|종합하면|결론적으로|정리하면)",
        r"\1",
        answer,
    )

    # 4. 기본 정리
    answer = answer.strip()

    # 5. 불필요한 줄바꿈 정리 (마크다운 유지하면서)
    answer = _normalize_blank_lines(answer)

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
    "strip_prose_bold",
]
