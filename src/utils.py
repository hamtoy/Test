import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles  # type: ignore[import-untyped]

from src.models import WorkflowResult


async def load_file_async(file_path: Path) -> str:
    """파일을 비동기로 읽어옵니다.

    Args:
        file_path: 읽을 파일 경로

    Returns:
        파일 내용 문자열

    Raises:
        FileNotFoundError: 파일이 없을 경우
        ValueError: 파일이 비어있을 경우
    """
    try:
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                raise ValueError(f"File is empty: {file_path}")
            return content.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Critical file missing: {file_path}")


def parse_raw_candidates(text: str) -> Dict[str, str]:
    """A:, B: 패턴을 사용하여 후보 답변 파싱 (Raw Text Parsing)."""
    candidates = {}
    # 패턴: 대문자 알파벳 + 콜론으로 시작하는 블록
    pattern = r"^([A-Z]):\s*(.+?)(?=^[A-Z]:|$)"

    matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)

    for match in matches:
        key = match.group(1)
        content = match.group(2).strip()
        candidates[key] = content

    # 구조화된 후보를 찾지 못한 경우 (Fallback)
    if not candidates:
        import logging

        logging.warning(
            "No structured candidates found. Treating entire text as Candidate A."
        )
        return {"A": text.strip()}

    return candidates


def clean_markdown_code_block(text: str) -> str:
    """Markdown 코드 블록을 제거하고 내용만 반환.

    Gemini의 JSON 모드는 신뢰할 수 있으므로 복잡한 정규식 대신 단순 제거를 사용합니다.
    """
    # Remove markdown code blocks if present (case-insensitive for JSON/json)
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    # No markdown found - return original (likely already clean JSON)
    return text.strip()


def _find_in_nested(obj: Any, target_key: str) -> Optional[Any]:
    """Recursively search dict/list structures for a key."""
    if isinstance(obj, dict):
        if target_key in obj:
            return obj[target_key]
        for value in obj.values():
            found = _find_in_nested(value, target_key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_in_nested(item, target_key)
            if found is not None:
                return found
    return None


def safe_json_parse(
    text: str, target_key: Optional[str] = None, raise_on_error: bool = False
) -> Optional[Any]:
    """안전한 JSON 파싱 헬퍼 함수.

    Best Practice: try-except, specific error handling, clean error reporting.

    Args:
        text: JSON 문자열 (마크다운 코드 블록 포함 가능)
        target_key: 추출할 특정 키 (Optional)
        raise_on_error: 에러 발생 시 예외 전파 여부

    Returns:
        파싱된 dict 또는 특정 키 값. 실패 시 None (raise_on_error=True면 예외 전파)
    """
    import logging

    logger = logging.getLogger("GeminiWorkflow")

    # Guard: 빈 입력
    if not text or not text.strip():
        message = "safe_json_parse: Empty input"
        if raise_on_error:
            raise ValueError(message)
        logger.warning(message)
        return None

    # Clean markdown
    cleaned = clean_markdown_code_block(text)

    # Guard: JSON 형식이 아님
    if not cleaned.strip().startswith("{"):
        message = "safe_json_parse: Not JSON format"
        if raise_on_error:
            raise ValueError(message)
        logger.debug(message)
        return None

    try:
        data = json.loads(cleaned)

        # Guard: dict가 아님
        if not isinstance(data, dict):
            message = "safe_json_parse: Parsed data is not a dict"
            if raise_on_error:
                raise ValueError(message)
            logger.warning(message)
            return None

        # 특정 키 추출
        if target_key:
            found = _find_in_nested(data, target_key)
            if found is None:
                logger.debug(f"safe_json_parse: Key '{target_key}' not found")
            return found

        return data

    except json.JSONDecodeError as e:
        message = f"safe_json_parse: JSON decode error - {e}"
        if raise_on_error:
            raise
        logger.warning(message)
        return None
    except Exception as e:
        message = f"safe_json_parse: Unexpected error - {e}"
        if raise_on_error:
            raise
        logger.error(message)
        return None


def write_cache_stats(path: Path, max_entries: int, entry: Dict[str, Any]) -> None:
    """
    Append cache/tokens stats to a JSONL file, trimming to max_entries.
    """
    max_entries = max(1, min(max_entries, 1000))
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    existing.append(entry)
    trimmed = existing[-max_entries:]

    with open(path, "w", encoding="utf-8") as f:
        for item in trimmed:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


async def load_checkpoint(path: Path) -> Dict[str, WorkflowResult]:
    """Load checkpoint entries indexed by query string (async, best-effort)."""
    if not path.exists():
        return {}
    records: Dict[str, WorkflowResult] = {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            async for line in f:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    wf = WorkflowResult(**payload)
                    records[wf.query] = wf
                except Exception:
                    continue
    except Exception:
        return {}
    return records


async def append_checkpoint(path: Path, result: WorkflowResult) -> None:
    """Append a single WorkflowResult to checkpoint JSONL (async, best-effort)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(result.model_dump(), ensure_ascii=False) + "\n")
    except Exception:
        # Non-fatal
        return
