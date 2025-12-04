"""공용 웹 API 유틸리티 함수와 상수."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

# 프로젝트 루트 경로 (templates, data 등 상대 경로 계산에 사용)
REPO_ROOT = Path(__file__).resolve().parents[2]
_OCR_CACHE: Optional[Tuple[Path, float, str]] = None

# 질의 유형 매핑 (QA/워크스페이스 공용)
QTYPE_MAP = {
    "global_explanation": "explanation",
    "explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target",
    "target": "target",
    "summary": "summary",
    "factual": "target",
    "general": "explanation",
}


def load_ocr_text(config: AppConfig) -> str:
    """data/inputs/input_ocr.txt 로드 (mtime 기반 간단 캐시 포함)."""
    global _OCR_CACHE
    ocr_path: Path = config.input_dir / "input_ocr.txt"
    if not ocr_path.exists():
        raise HTTPException(status_code=404, detail="OCR 파일이 없습니다.")

    mtime = ocr_path.stat().st_mtime
    if _OCR_CACHE and _OCR_CACHE[0] == ocr_path and _OCR_CACHE[1] == mtime:
        return _OCR_CACHE[2]

    text = ocr_path.read_text(encoding="utf-8").strip()
    _OCR_CACHE = (ocr_path, mtime, text)
    return text


def save_ocr_text(config: AppConfig, text: str) -> None:
    """OCR 텍스트 저장 (이미지 분석 후)."""
    ocr_path = config.input_dir / "input_ocr.txt"
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    ocr_path.write_text(text, encoding="utf-8")


def log_review_session(
    mode: Literal["inspect", "edit"],
    question: str,
    answer_before: str,
    answer_after: str,
    edit_request_used: str,
    inspector_comment: str,
    *,
    base_dir: Optional[Path] = None,
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
    text = re.sub(r"(\\d)\\s*[\\r\\n]+-\\s*(\\d)", r"\\1.\\2", text)

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
    query: Optional[str], answer: Optional[str], edit_request: Optional[str]
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

    if has_edit:
        if has_query and has_answer:
            return "edit_both"
        if has_query:
            return "edit_query"
        if has_answer:
            return "edit_answer"

    if not has_query and has_answer:
        return "query_generation"

    if has_query and not has_answer:
        return "answer_generation"

    return "rewrite"


def postprocess_answer(answer: str, qtype: str) -> str:
    """답변 후처리 - 서식 규칙 위반 자동 수정."""
    # 1. 태그 제거
    answer = strip_output_tags(answer)
    # 1.1 숫자 포맷 깨짐 복원
    answer = fix_broken_numbers(answer)
    # 1.2 볼드 마커 정규화: 짝이 안 맞는 **텍스트* / *텍스트** 제거
    # Case: **Text* \n * (Broken bold across lines)
    answer = re.sub(r"\*\*([^*]+)\*\s*\n\s*\*", r"**\1**", answer)
    answer = re.sub(r"\*\*([^*]+)\*(?!\*)", r"\1", answer)
    answer = re.sub(r"\*([^*]+)\*\*", r"\1", answer)
    answer = re.sub(r"\*\*(.*?)\*\*", r"**\1**", answer, flags=re.DOTALL)
    answer = re.sub(r"(?<!\*)\*(?!\*)", "", answer)

    # 2. ###/## 소제목 → **소제목** + 줄바꿈
    answer = re.sub(r"\s*###\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)
    answer = re.sub(r"\s*##\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)

    # 3. 별표 불릿(*) → 하이픈(-) + 줄바꿈 보장
    answer = re.sub(r"\s*\*\s+\*\*([^*]+)\*\*:", r"\n- **\1**:", answer)
    answer = re.sub(r"\s*\*\s+", r"\n- ", answer)

    # 4. 질의 유형별 후처리
    if qtype in {"target_short", "target_long"}:
        # 불릿/개행 제거 후 짧은 문장으로 압축
        lines = [
            re.sub(r"^[\-\*\u2022]\s*", "", line).strip(" -•\t")
            for line in answer.splitlines()
            if line.strip()
        ]
        if lines:
            answer = ". ".join(lines)

        sentences = [
            s.strip()
            for s in re.split(r"(?<!\d)\.(?!\d)", answer.replace("\n", ". "))
            if s.strip()
        ]
        if sentences:
            max_sentences = 1 if qtype == "target_short" else 4
            answer = ". ".join(sentences[:max_sentences]).strip()
        else:
            answer = answer.strip()
        answer = re.sub(r"\s+", " ", answer).strip()

        # 타겟 유형은 마크다운 제거 강제
        answer = re.sub(r"\*\*(.*?)\*\*", r"\1", answer, flags=re.DOTALL)
        answer = re.sub(r"\*(.*?)\*", r"\1", answer)
        answer = re.sub(r"[_]{1,2}(.*?)[_]{1,2}", r"\1", answer)

        if qtype == "target_short" and answer.endswith("."):
            answer = answer[:-1].strip()

    elif qtype in {"global_explanation", "explanation", "reasoning"}:
        # 서술문 앞의 불릿(-, •) 제거 및 문단 정리
        paragraph_lines: list[str] = []
        for line in answer.splitlines():
            stripped = line.strip()
            if not stripped:
                paragraph_lines.append("")
                continue
            cleaned = re.sub(r"^[-•]\s*", "", stripped)
            paragraph_lines.append(cleaned)
        # 빈 줄 기준으로 문단 분리 후, 단락 내 개행을 공백으로 치환
        paragraphs: list[str] = []
        for paragraph in "\n".join(paragraph_lines).split("\n\n"):
            if not paragraph.strip():
                continue
            # 콜론 뒤 개행 제거 (예: 제목\n: 내용 → 제목: 내용)
            paragraph = re.sub(r"\n\s*:\s*", ": ", paragraph)
            paragraph = re.sub(r"\s*\n\s*", " ", paragraph)
            paragraph = re.sub(r"\s+", " ", paragraph).strip(" -•\t")
            if qtype == "reasoning":
                paragraph = re.sub(
                    r"^(근거|추론|결론|배경|요약)\s*[:\-]\s*",
                    "",
                    paragraph,
                    flags=re.IGNORECASE,
                )
            paragraphs.append(paragraph)
        answer = "\n\n".join(paragraphs)

    # 5. 공통 정리: 남은 불릿 및 과도한 개행 제거 (마크다운은 보존)
    answer = answer.replace("*", "")  # 남은 별표(강조 아님) 제거
    answer = re.sub(r"^[-•]\s*", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"^#+\s*", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"\n{3,}", "\n\n", answer)

    return answer.strip()


__all__ = [
    "QTYPE_MAP",
    "REPO_ROOT",
    "detect_workflow",
    "fix_broken_numbers",
    "load_ocr_text",
    "log_review_session",
    "postprocess_answer",
    "save_ocr_text",
    "strip_output_tags",
]
