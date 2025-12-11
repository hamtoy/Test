import asyncio
import concurrent.futures
import json
import re
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import aiofiles

from src.core.models import WorkflowResult

T = TypeVar("T")


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """동기 컨텍스트에서 안전하게 코루틴을 실행합니다.

    이미 실행 중인 이벤트 루프가 있으면 별도 스레드에서 새 루프로 실행하고,
    없는 경우에는 새 루프를 생성해 실행합니다.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def run_in_thread() -> T:
        """새 이벤트 루프를 가진 워커 스레드에서 코루틴 실행."""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result()


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
        # Use utf-8-sig to automatically handle UTF-8 BOM (common on Windows)
        async with aiofiles.open(file_path, encoding="utf-8-sig") as f:
            content = await f.read()
            if not content.strip():
                raise ValueError(f"File is empty: {file_path}")
            return content.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Critical file missing: {file_path}")


def parse_raw_candidates(text: str) -> dict[str, str]:
    """A:, B: 패턴을 사용하여 후보 답변 파싱 (Raw Text Parsing)."""
    candidates = {}
    # 패턴: 대문자 알파벳 + 콜론으로 시작하는 블록
    pattern = r"^([A-Z]):\s*(.+?)(?=(?:^[A-Z]:)|$)"

    matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)

    for match in matches:
        key = match.group(1)
        content = match.group(2).strip()
        candidates[key] = content

    import logging
    import re as _re

    def _split_chunks(raw: str) -> dict[str, str]:
        chunks = [
            chunk.strip()
            for chunk in _re.split(r"\n-{3,}\n|\n{2,}", raw)
            if chunk.strip() and not _re.fullmatch(r"-+", chunk.strip())
        ]
        if len(chunks) >= 2:
            labels = ["A", "B", "C"]
            return dict(zip(labels, chunks))
        return {}

    # 구조화된 후보를 찾지 못한 경우 먼저 구분자로 split 시도 후 최종 fallback
    if not candidates:
        split_candidates = _split_chunks(text)
        if split_candidates:
            return split_candidates
        logging.warning(
            "No structured candidates found. Treating entire text as Candidate A.",
        )
        return {"A": text.strip()}

    # 추가 보조: A만 있는 경우, 구분자(--- 혹은 빈 줄 2개 이상)로 나눠 A/B/C 추론
    if set(candidates.keys()) == {"A"}:
        split_candidates = _split_chunks(text)
        if split_candidates:
            candidates = split_candidates

    return candidates


def clean_markdown_code_block(text: str) -> str:
    """Markdown 코드 블록을 제거하고 내용만 반환.

    Gemini의 JSON 모드는 신뢰할 수 있으므로 복잡한 정규식 대신 단순 제거를 사용합니다.
    """
    # Remove markdown code blocks if present (case-insensitive for JSON/json)
    pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
    match = pattern.search(text)

    if match:
        return match.group(1).strip()

    # No markdown found - return original (likely already clean JSON)
    return text.strip()


def _find_in_nested(obj: Any, target_key: str) -> Any | None:
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
    text: str,
    target_key: str | None = None,
    raise_on_error: bool = False,
) -> Any | None:
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
    except (TypeError, ValueError) as e:
        message = f"safe_json_parse: Invalid JSON structure - {e}"
        if raise_on_error:
            raise
        logger.error(message)
        return None
    except Exception as e:
        message = f"safe_json_parse: Unexpected error - {e}"
        if raise_on_error:
            raise
        logger.error(message)
        return None


def write_cache_stats(path: Path, max_entries: int, entry: dict[str, Any]) -> None:
    """Append cache/tokens stats to a JSONL file, trimming to max_entries."""
    max_entries = max(1, min(max_entries, 1000))
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
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
        f.writelines(json.dumps(item, ensure_ascii=False) + "\n" for item in trimmed)


async def load_checkpoint(path: Path) -> dict[str, WorkflowResult]:
    """Load checkpoint entries indexed by query string (async, best-effort)."""
    if not path.exists():
        return {}
    records: dict[str, WorkflowResult] = {}
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            async for line in f:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    wf = WorkflowResult(**payload)
                    records[wf.query] = wf
                except (TypeError, ValueError):
                    continue
    except OSError:
        return {}
    return records


async def append_checkpoint(path: Path, result: WorkflowResult) -> None:
    """Append a single WorkflowResult to checkpoint JSONL (async, best-effort)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(result.model_dump(), ensure_ascii=False) + "\n")
    except OSError:
        return


__all__ = [
    "_find_in_nested",
    "append_checkpoint",
    "clean_markdown_code_block",
    "load_checkpoint",
    "load_file_async",
    "parse_raw_candidates",
    "run_async_safely",
    "safe_json_parse",
    "write_cache_stats",
]
