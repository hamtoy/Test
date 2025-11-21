# src/data_loader.py

import json
import logging
from pathlib import Path
from typing import Dict

from src.utils import load_file_async, parse_raw_candidates

logger = logging.getLogger("GeminiWorkflow")

async def load_input_data(base_dir: Path, ocr_filename: str, cand_filename: str) -> tuple[str, Dict[str, str]]:
    """
    [Smart Loader] 확장자나 형식을 가리지 않고 최선을 다해 데이터를 로드합니다.
    1. JSON 파싱 시도 -> 성공 시 반환
    2. 실패 시 -> Raw Text (A:, B:) 파싱 시도
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
            logger.info(f"Format Detection: Valid JSON detected in '{cand_filename}' ({len(candidates)} candidates)")
        else:
            logger.warning(f"Format Detection: JSON parsed but empty or invalid type in '{cand_filename}'")
    except json.JSONDecodeError as e:
        logger.info(f"Format Detection: JSON parse failed ({e}). Trying Raw Text format...")
    except Exception as e:
        logger.warning(f"Format Detection: Unexpected error during JSON parse: {e}")

    # JSON 파싱에 실패했거나 결과가 없으면 Regex 파싱 실행
    if not candidates:
        logger.info(f"Format Detection: Trying Raw Text parsing for '{cand_filename}'")
        candidates = parse_raw_candidates(cand_text)

    # [Final Validation] 그래도 없으면 에러
    if not candidates:
        raise ValueError(
            f"데이터 파싱 실패: '{cand_filename}'의 형식을 인식할 수 없습니다.\n"
            f"1. 올바른 JSON 형식을 사용하거나 ({{ \"A\": \"...\" }})\n"
            f"2. 텍스트 형식(A: 답변...)을 사용하세요."
        )

    return ocr_text, candidates
