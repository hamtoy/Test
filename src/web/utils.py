"""공용 웹 API 유틸리티 함수와 상수."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

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


def fix_broken_numbers(text: str) -> str:
    r"""잘못 분리된 숫자/소수 표현을 복원한다.

    예:
        "61\n- 7만건" -> "61.7만건"
        "873\n- 3만 건" -> "873.3만 건"
    """
    # 패턴 1: 숫자 + 줄바꿈 + 불릿 + 숫자 → 소수점으로 병합
    text = re.sub(r"(\d)\s*[\r\n]+-\s*(\d)", r"\1.\2", text)

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

    def _limit_words(text: str, max_words: int) -> str:
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])
        return text

    def _normalize_ending_punctuation(text: str) -> str:
        """Replace ellipsis with period, or add period if missing."""
        if text:
            if text.endswith("..."):
                return text[:-3] + "."
            elif not text.endswith("."):
                return text + "."
        return text

    def _ensure_period_preserve_ellipsis(text: str) -> str:
        """Add period if missing, but preserve existing ellipsis."""
        if text and not text.endswith(".") and not text.endswith("..."):
            return text + "."
        return text

    # 실제 사용되는 4가지 질질 타입별 설정
    config: dict[str, dict[str, int]] = {
        # 1. 전체 마모뇌 설명: No word limit (length controlled by prompt: 1000-1500 chars)
        # 2. 추론 (reasoning): 제약 제거 - 프롬프트 레벨에서 길이 제어
        #    Gemini의 원래 생성 길이를 사용하여 답변 손실 방지 (28-50% 손실 문제 해결)
    }

    def _split_sentences(text: str) -> list[str]:
        """Split sentences carefully, avoiding split on decimal points."""
        # 1. Protect decimal patterns temporarily (e.g. 3.5, 3. 5)
        protected = re.sub(r"(\d)\.(\d)", r"\1_DOT_\2", text)
        protected = re.sub(r"(\d)\.\s+(\d)", r"\1_DOT_SPACE_\2", protected)

        # 2. Split by "."
        sentences = [s.strip() for s in protected.split(".") if s.strip()]

        # 3. Restore patterns
        final_sentences = []
        for s in sentences:
            restored = s.replace("_DOT_SPACE_", ". ").replace("_DOT_", ".")
            final_sentences.append(restored)

        return final_sentences

    if normalized_qtype in config:
        limits = config[normalized_qtype]

        # 1단계: 문장 제한
        sentences = _split_sentences(answer)
        if sentences:
            sentences = sentences[: limits["max_sentences"]]
            answer = ". ".join(sentences)
            if answer and not answer.endswith("."):
                answer += "."

        # 2단계: 단어 수 제한 (최종 조정)
        answer = _limit_words(answer, limits["max_words"])

    elif normalized_qtype == "reasoning":
        # reasoning: 3-4문장, 최대 200단어로 제한
        def _limit_words_reasoning(text: str, max_words: int) -> str:
            words = text.split()
            if len(words) > max_words:
                text = " ".join(words[:max_words])
            return text

        sentences = _split_sentences(answer)
        if sentences and len(sentences) > 5:
            sentences = sentences[:5]
            answer = ". ".join(sentences)
            if answer and not answer.endswith("."):
                answer += "."
        answer = _limit_words_reasoning(answer, 200)
        # For reasoning: replace ellipsis with period
        answer = _normalize_ending_punctuation(answer)

    elif normalized_qtype == "explanation":
        # global_explanation: No word/sentence limits, but ensure period at end
        # Preserve ellipsis if present, only add period when both period and ellipsis are missing
        answer = _ensure_period_preserve_ellipsis(answer)

        # Dynamic max length enforcement (if provided)
        if max_length and len(answer) > max_length:
            # Cut at maximum length first
            truncated = answer[:max_length]

            # Try to find the last sentence ending within the limit
            # (Check for period within the last 20% or last 100 chars to avoid cutting too much)
            last_period = truncated.rfind(".")
            if last_period > -1 and last_period > len(truncated) - 150:
                answer = truncated[: last_period + 1]
            else:
                # If no suitable period found, we might be cutting a very long sentence.
                # For now, just force cut and add ellipsis if strictly needed,
                # but usually answer should have periods.
                # Let's trust the cut or try to keep it slightly over if no period found?
                # User wants STRICT max. So we force cut if no period.
                if last_period > -1:
                    answer = truncated[: last_period + 1]
                else:
                    answer = truncated + "."

    elif qtype == "target":
        # 타겟 질질: 단답형 vs 서술형 자동 판단
        word_count = len(answer.split())

        if word_count < 15:
            # Short target answers preserved as-is without automatic punctuation
            answer = _limit_words(answer, 50)
        else:
            # 4. target long: 200단어, 최대 6문장
            sentences = _split_sentences(answer)
            if sentences:
                sentences = sentences[:6]
                answer = ". ".join(sentences)
                if answer and not answer.endswith("."):
                    answer += "."
            answer = _limit_words(answer, 200)

    return answer


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
        # 1. ### 헤더 제거 (### 뒤의 공백까지 제거)
        # 예: "### 제목" → "제목"
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # 2. *italic* 제거하되 **bold**는 보호
        # 2-1. **bold**를 고유한 임시 토큰으로 보호 (충돌 방지)
        bold_placeholder = "##BOLD_PLACEHOLDER_8A3F2E1C##"
        text = text.replace("**", bold_placeholder)

        # 2-2. 홑별표 제거 (italic 제거)
        # 패턴: *텍스트* → 텍스트
        # [^*]+? : 별표가 아닌 문자들을 최소 매칭 (italic 내용만 추출)
        text = re.sub(r"\*([^*]+?)\*", r"\1", text)

        # 남은 홑별표도 제거 (짝이 맞지 않는 경우)
        text = text.replace("*", "")

        # 2-3. 임시 토큰을 **bold**로 복원
        text = text.replace(bold_placeholder, "**")

        return text

    def _add_markdown_structure(text: str, qtype: str) -> str:
        """평문에 마크다운 구조 자동 추가.

        패턴 분석:
        1. 소제목: 단독 줄 + 다음 줄에 '항목명:' 패턴 → **굵은 소제목**
        2. 불릿 항목: '항목명: 설명' 패턴 → - **항목명**: 설명

        target 타입은 평문 유지 (마크다운 추가하지 않음).
        """
        normalized = QTYPE_MAP.get(qtype, qtype)

        # explanation 타입에만 마크다운 구조 추가
        # reasoning/target 타입은 평문 유지 (마크다운 자동 추가하지 않음)
        if normalized != "explanation":
            return text

        lines = text.split("\n")
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 빈 줄은 그대로 유지
            if not stripped:
                result.append(line)
                i += 1
                continue

            # 이미 마크다운이 적용된 경우 스킵
            if stripped.startswith("**") or stripped.startswith("- **"):
                result.append(line)
                i += 1
                continue

            # 이미 불릿이 있는 경우: 항목명에 볼드 추가
            if stripped.startswith("- "):
                bullet_content = stripped[2:].strip()
                if ": " in bullet_content and not bullet_content.startswith("**"):
                    # "- 항목명: 설명" → "- **항목명**: 설명"
                    colon_idx = bullet_content.index(": ")
                    item_name = bullet_content[:colon_idx]
                    item_desc = bullet_content[colon_idx + 2 :]
                    result.append(f"- **{item_name}**: {item_desc}")
                else:
                    result.append(line)
                i += 1
                continue

            # 소제목 감지: 현재 줄이 짧고, 다음 줄에 "항목명:" 패턴이 있으면
            is_section_header = False
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # 다음 줄이 "항목명: 설명" 패턴이고, 현재 줄이 50자 이하 콜론 없으면 소제목
                if (
                    ": " in next_line
                    and not next_line.startswith("-")
                    and len(stripped) <= 50
                    and ": " not in stripped
                ):
                    is_section_header = True

            if is_section_header:
                # 소제목에 볼드 추가
                result.append(f"**{stripped}**")
                i += 1
                continue

            # "항목명: 설명" 패턴 감지 (불릿 없는 경우)
            if ": " in stripped:
                colon_idx = stripped.index(": ")
                potential_name = stripped[:colon_idx]
                # 항목명이 30자 이하이고 마침표가 없으면 불릿 항목으로 변환
                if len(potential_name) <= 30 and "." not in potential_name:
                    item_desc = stripped[colon_idx + 2 :]
                    result.append(f"- **{potential_name}**: {item_desc}")
                    i += 1
                    continue

            # 그 외의 경우 그대로 유지
            result.append(line)
            i += 1

        return "\n".join(result)

    # 1. 태그 제거
    answer = strip_output_tags(answer)
    answer = _strip_code_and_links(answer)

    # 2. 숫자 포맷 깨짐 복원
    answer = fix_broken_numbers(answer)

    # 3. 허용되지 않은 마크다운 제거 (CSV 규칙 준수)
    answer = _remove_unauthorized_markdown(answer)

    # 4. 기본 정리
    answer = answer.strip()

    # 5. 불필요한 줄바꿈 정리 (마크다운 유지하면서)
    # 연속된 빈 줄은 최대 2개까지만 유지 (= 최대 3개의 \n 문자)
    # 예: "텍스트\n\n\n\n줄바꿈" (4개 \n) → "텍스트\n\n\n줄바꿈" (3개 \n)
    lines = answer.split("\n")
    cleaned_lines = []
    empty_count = 0

    for line in lines:
        if line.strip() == "":
            empty_count += 1
            if empty_count <= 2:
                cleaned_lines.append(line)
        else:
            empty_count = 0
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
    "save_ocr_text",
    "strip_output_tags",
]
