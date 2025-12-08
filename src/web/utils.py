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


def apply_answer_limits(answer: str, qtype: str) -> str:
    """질의 타입별로 답변 길이 제한 적용.

    4가지 실제 질질 타입:
    1. global_explanation: 질질 1 (전체 마모뇌) - 프롬프트로 제어 (1000-1500자)
    2. reasoning: 질질 2 (추론) - 프롬프트로 제어 (제약 없음, 답변 손실 방지)
    3. target (short): 질질 3 (숫자/명칭) - 단답형 자동 탐지
    4. target (long): 질질 4 (강조) - 서술형 자동 탐지
    """

    def _limit_words(text: str, max_words: int) -> str:
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])
        return text

    # 실제 사용되는 4가지 질질 타입별 설정
    config: dict[str, dict[str, int]] = {
        # 1. 전체 마모뇌 설명: No word limit (length controlled by prompt: 1000-1500 chars)
        # 2. 추론: 제약 제거 - 프롬프트 레벨에서 길이 제어 (더 정교함)
        #    reasoning은 Gemini의 원래 생성 길이 사용하여 답변 손실 방지
        # "reasoning": {"max_words": 100, "max_sentences": 4},  # 기존 제약 (28-50% 손실)
    }

    if qtype in config:
        limits = config[qtype]

        # 1단계: 문장 제한
        sentences = [s.strip() for s in answer.split(".") if s.strip()]
        if sentences:
            sentences = sentences[: limits["max_sentences"]]
            answer = ". ".join(sentences)
            if answer and not answer.endswith("."):
                answer += "."

        # 2단계: 단어 수 제한 (최종 조정)
        answer = _limit_words(answer, limits["max_words"])

    elif qtype == "reasoning":
        # reasoning: No word/sentence limits (prevent 28-50% content loss)
        # Only ensure period at end for consistency
        # Replace "..." with "." for proper sentence ending
        answer = answer.rstrip()
        if answer.endswith("..."):
            answer = answer[:-3] + "."
        elif answer and not answer.endswith("."):
            answer += "."

    elif qtype == "global_explanation":
        # global_explanation: No word/sentence limits, but ensure period at end
        if answer and not answer.endswith("."):
            answer += "."

    elif qtype == "target":
        # 타겟 질질: 단답형 vs 서술형 자동 판단
        word_count = len(answer.split())

        if word_count < 15:
            # 3. target short: 매우 간결
            answer = _limit_words(answer, 50)
        else:
            # 4. target long: 180단어, 최대 5문장
            sentences = [s.strip() for s in answer.split(".") if s.strip()]
            if sentences:
                sentences = sentences[:5]
                answer = ". ".join(sentences)
                if answer and not answer.endswith("."):
                    answer += "."
            answer = _limit_words(answer, 180)

    return answer


def postprocess_answer(answer: str, qtype: str) -> str:
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

    # 6. 길이 제한 적용
    answer = apply_answer_limits(answer, qtype)

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
