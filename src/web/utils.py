"""공용 웹 API 유틸리티 함수와 상수."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

# 프로젝트 루트 경로 (templates, data 등 상대 경로 계산에 사용)
REPO_ROOT = Path(__file__).resolve().parents[2]

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
    """data/inputs/input_ocr.txt 로드."""
    ocr_path: Path = config.input_dir / "input_ocr.txt"
    if not ocr_path.exists():
        raise HTTPException(status_code=404, detail="OCR 파일이 없습니다.")
    return ocr_path.read_text(encoding="utf-8").strip()


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


def detect_workflow(
    query: str, answer: str, edit_request: Optional[str]
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

    # 2. ###/## 소제목 → **소제목** + 줄바꿈
    answer = re.sub(r"\s*###\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)
    answer = re.sub(r"\s*##\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)

    # 3. 별표 불릿(*) → 하이픈(-) + 줄바꿈 보장
    answer = re.sub(r"\s*\*\s+\*\*([^*]+)\*\*:", r"\n- **\1**:", answer)
    answer = re.sub(r"\s*\*\s+", r"\n- ", answer)

    # 4. 질의 유형별 후처리
    if qtype in {"target_short", "target_long"}:
        # 문장 단위로 분리 후 정리
        sentences = [s.strip() for s in answer.split(".") if s.strip()]
        answer = "\n".join(f"- {s}" for s in sentences)

    return answer.strip()


__all__ = [
    "QTYPE_MAP",
    "REPO_ROOT",
    "detect_workflow",
    "load_ocr_text",
    "log_review_session",
    "postprocess_answer",
    "save_ocr_text",
    "strip_output_tags",
]
