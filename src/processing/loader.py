# src/processing/loader.py

import json
import logging
from pathlib import Path
from typing import Dict, Set

from src.config import AppConfig
from src.exceptions import ValidationFailedError
from src.utils import load_file_async, parse_raw_candidates

logger = logging.getLogger("GeminiWorkflow")


def validate_candidates(candidates: Dict[str, str]) -> None:
    """후보 답변 구조와 내용을 검증합니다."""
    required_keys: Set[str] = {"A", "B", "C"}
    actual_keys = set(candidates.keys())

    if not required_keys.issubset(actual_keys):
        missing = required_keys - actual_keys
        raise ValidationFailedError(
            f"Candidates missing required keys: {missing}. "
            f"Expected at least {required_keys}, got {actual_keys or 'none'}"
        )

    for key, value in candidates.items():
        if not value or not value.strip():
            raise ValidationFailedError(f"Candidate '{key}' has empty content")


async def load_input_data(
    base_dir: Path, ocr_filename: str, cand_filename: str
) -> tuple[str, Dict[str, str]]:
    """확장자나 형식을 가리지 않고 최선을 다해 데이터를 로드합니다 (Smart Loader).

    1. JSON 파싱 시도 -> 성공 시 반환
    2. 실패 시 -> Raw Text (A:, B:) 파싱 시도

    Args:
        base_dir: 기본 디렉토리 경로
        ocr_filename: OCR 파일명
        cand_filename: 후보 답변 파일명

    Returns:
        (OCR 텍스트, 후보 답변 딕셔너리) 튜플

    Raises:
        FileNotFoundError: 파일이 없을 경우
        ValueError: 파일이 비어있거나 파싱 실패 시
    """
    ocr_path = base_dir / ocr_filename
    cand_path = base_dir / cand_filename

    # 1. 파일 존재 확인 (Fail Fast)
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR file missing: {ocr_path}")
    if not cand_path.exists():
        raise FileNotFoundError(f"Candidate file missing: {cand_path}")

    # 2. OCR 텍스트 로드
    ocr_text = await load_file_async(ocr_path)
    if not ocr_text:
        raise ValueError(f"OCR file is empty: {ocr_path}")

    # 3. 후보 답변 로드 (Hybrid Parsing with Safety)
    cand_text = await load_file_async(cand_path)

    if not cand_text or not cand_text.strip():
        raise ValueError(f"Candidate file is empty: {cand_path}")

    candidates = {}

    # [Strategy 1] JSON으로 간주하고 파싱 시도 (안전한 파싱)
    try:
        data = json.loads(cand_text)
        if isinstance(data, dict) and data:
            candidates = data
            logger.info(
                f"Format Detection: Valid JSON in '{cand_filename}' "
                f"({len(candidates)} candidates)"
            )
        else:
            logger.warning(
                f"Format Detection: JSON parsed but empty/invalid type "
                f"in '{cand_filename}'"
            )
    except json.JSONDecodeError as e:
        logger.warning(
            f"Format Detection: JSON parse failed in '{cand_filename}' "
            f"at line {e.lineno}, column {e.colno}: {e.msg}. "
            f"Trying Raw Text format..."
        )
    except (TypeError, ValueError) as e:
        logger.warning(f"Format Detection: Invalid JSON structure ({e}).")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Format Detection: Unexpected JSON parse error: {e}")

    # JSON 파싱에 실패했거나 결과가 없으면 Regex 파싱 실행
    if not candidates:
        logger.info(f"Format Detection: Trying Raw Text parsing for '{cand_filename}'")
        candidates = parse_raw_candidates(cand_text)

    # [Final Validation] 그래도 없으면 에러
    if not candidates:
        raise ValueError(
            f"데이터 파싱 실패: '{cand_filename}'의 형식을 인식할 수 없습니다.\n"
            f'1. 올바른 JSON 형식을 사용하거나 ({{ "A": "..." }})\n'
            f"2. 텍스트 형식(A: 답변...)을 사용하세요."
        )

    # Validate structure and content
    validate_candidates(candidates)

    return ocr_text, candidates


async def reload_data_if_needed(
    config: AppConfig, ocr_filename: str, cand_filename: str, interactive: bool = False
) -> tuple[str, Dict[str, str]]:
    """
    OCR/후보 데이터를 재로드하는 래퍼 함수. interactive 플래그는 향후 프롬프트를 위해 예약됨.
    """
    return await load_input_data(config.input_dir, ocr_filename, cand_filename)
