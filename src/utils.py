import json
import re
import aiofiles  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any, Dict, Optional


async def load_file_async(file_path: Path) -> str:
    """[Async I/O] 파일을 비동기로 읽어옵니다. (Fail Fast: 에러 발생 시 예외 전파)"""
    try:
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                raise ValueError(f"File is empty: {file_path}")
            return content.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Critical file missing: {file_path}")


def parse_raw_candidates(text: str) -> Dict[str, str]:
    """[Raw Text Parsing] A:, B: 패턴을 사용하여 후보 답변 파싱"""
    candidates = {}
    # 패턴: 대문자 알파벳 + 콜론으로 시작하는 블록
    pattern = r"^([A-Z]):\s*(.+?)(?=^[A-Z]:|$)"

    matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)

    for match in matches:
        key = match.group(1)
        content = match.group(2).strip()
        candidates[key] = content

    # [Fallback] 구조화된 후보를 찾지 못한 경우
    if not candidates:
        import logging

        logging.warning(
            "No structured candidates found. Treating entire text as Candidate A."
        )
        return {"A": text.strip()}

    return candidates


def clean_markdown_code_block(text: str) -> str:
    """
    [Simplified & Safe] Trust Gemini JSON Mode
    Remove markdown code blocks, then return as-is.
    Gemini's JSON mode is reliable - complex regex can break valid JSON.
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
    """
    [Centralized JSON Parsing] 안전한 JSON 파싱 헬퍼 함수
    Best Practice: try-except, specific error handling, clean error reporting

    Args:
        text: JSON 문자열 (마크다운 코드 블록 포함 가능)
        target_key: 추출할 특정 키 (Optional)

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
