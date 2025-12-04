"""QA generation module with dependency injection and safe imports.

This refactor removes module-level side effects (sys.exit, env lookups, API calls)
and provides a class-based generator that can be instantiated with injected
configuration and client dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, List, Sequence

from openai import OpenAI

from src.config.settings import AppConfig

LOGGER = logging.getLogger(__name__)

DEFAULT_PROMPT_DIR = Path(__file__).resolve().parents[2] / "templates" / "prompts"
DEFAULT_QUERY_PROMPT = DEFAULT_PROMPT_DIR / "query_generation.txt"
DEFAULT_ANSWER_PROMPT = DEFAULT_PROMPT_DIR / "answer_generation.txt"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class QAGenerator:
    """LLM 기반 QA 생성기.

    프롬프트 경로와 LLM 클라이언트를 주입할 수 있도록 구성하여 테스트 가능성을 높이고
    모듈 로드시 부작용을 제거했다.
    """

    def __init__(
        self,
        config: AppConfig,
        *,
        client: OpenAI | None = None,
        query_prompt_path: Path | str | None = None,
        answer_prompt_path: Path | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize QA generator with configuration and optional dependencies.

        Args:
            config: Application configuration containing API key and model settings
            client: Optional pre-configured OpenAI client (creates default if None)
            query_prompt_path: Custom path to query generation prompt template
            answer_prompt_path: Custom path to answer generation prompt template
            logger: Optional logger instance (uses module logger if None)
        """
        self.config = config
        self.logger = logger or LOGGER

        prompt_dir = DEFAULT_PROMPT_DIR
        self.query_prompt_path = (
            Path(query_prompt_path) if query_prompt_path else DEFAULT_QUERY_PROMPT
        )
        self.answer_prompt_path = (
            Path(answer_prompt_path) if answer_prompt_path else DEFAULT_ANSWER_PROMPT
        )

        prompt_dir.mkdir(parents=True, exist_ok=True)
        self.query_system_prompt = self._load_prompt(self.query_prompt_path)
        self.answer_system_prompt = self._load_prompt(self.answer_prompt_path)

        self.client = client or self._build_client()

    def _build_client(self) -> OpenAI:
        """생성자에서 주입되지 않은 경우 OpenAI 호환 Gemini 클라이언트 생성."""
        return OpenAI(api_key=self.config.api_key, base_url=DEFAULT_BASE_URL)

    def _load_prompt(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content or ""

    def generate_questions(self, ocr_text: str, query_count: int = 4) -> List[str]:
        """OCR 텍스트로부터 다채로운 질의 목록 생성."""
        if query_count not in {3, 4}:
            raise ValueError("query_count must be 3 or 4")

        type_instruction = (
            "Generate the following question types in Korean, in order:\n"
            "1. Overview/explanation question covering the whole context\n"
            "2. Reasoning/forecast question grounded in evidence in the text\n"
            "3. Target short fact question (specific number/name)\n"
        )
        if query_count == 4:
            type_instruction += (
                "4. Target long descriptive question focusing on detailed narrative\n"
            )

        user_prompt = (
            "<input_text>\n"
            f"{ocr_text.strip()}\n"
            "</input_text>\n\n"
            "<request>\n"
            f"{type_instruction}\n"
            "Return as a numbered list.\n"
            "</request>"
        )

        raw_questions = self._call_llm(self.query_system_prompt, user_prompt)
        if not raw_questions:
            raise RuntimeError("질의 생성 실패 (LLM 응답 없음)")

        return self._parse_questions(raw_questions)

    def generate_answers(
        self, ocr_text: str, questions: Sequence[str]
    ) -> List[dict[str, Any]]:
        """질의 목록에 대한 답변 생성."""
        results: List[dict[str, Any]] = []
        for idx, question in enumerate(questions, start=1):
            answer_prompt = (
                "<input_text>\n"
                f"{ocr_text.strip()}\n"
                "</input_text>\n\n"
                "<instruction>\n"
                f"{question}\n"
                "</instruction>"
            )
            answer = self._call_llm(self.answer_system_prompt, answer_prompt)
            results.append({"id": idx, "question": question, "answer": answer})
        return results

    def generate_qa(self, ocr_text: str, query_count: int = 4) -> List[dict[str, Any]]:
        """질의/답변 쌍을 생성 후 리스트로 반환."""
        questions = self.generate_questions(ocr_text, query_count=query_count)
        return self.generate_answers(ocr_text, questions)

    def save_results(
        self,
        qa_pairs: Iterable[dict[str, Any]],
        *,
        json_path: Path | str,
        markdown_path: Path | str | None = None,
    ) -> None:
        """결과를 JSON/Markdown으로 저장."""
        pairs_list = list(qa_pairs)
        json_file = Path(json_path)
        json_file.parent.mkdir(parents=True, exist_ok=True)
        with open(str(json_file), "w", encoding="utf-8") as f_json:
            f_json.write(json.dumps(pairs_list, ensure_ascii=False, indent=2))

        if markdown_path:
            md_file = Path(markdown_path)
            md_file.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = []
            lines.append(f"# QA Results ({len(pairs_list)} pairs)\n")
            for item in pairs_list:
                lines.append(f"## Q{item.get('id')}. {item.get('question')}\n")
                lines.append(f"{item.get('answer')}\n")
                lines.append("---\n")
            with open(str(md_file), "w", encoding="utf-8") as f_md:
                f_md.write("\n".join(lines))

    @staticmethod
    def _parse_questions(raw: str) -> List[str]:
        """생성된 텍스트에서 질문만 추출."""
        questions: List[str] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if (
                not line
                or line.startswith("#")
                or line.startswith("```")
                or line.startswith("<")
            ):
                continue
            clean_line = re.sub(r"^\d+\.\s*", "", line)
            clean_line = clean_line.replace('"', "").replace("'", "")
            if clean_line.strip():
                questions.append(clean_line)
        return questions


def _load_default_ocr_text() -> str:
    """Try to load OCR text from data/inputs/input_ocr.txt for manual runs."""
    default_path = (
        Path(__file__).resolve().parents[2] / "data" / "inputs" / "input_ocr.txt"
    )
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")
    return "Provide OCR text here."


def _run_example() -> None:
    """Run the example QA generation flow (used for script execution and tests)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.startswith("AIza"):
        os.environ["GEMINI_API_KEY"] = "AIza" + ("x" * 35)
    # 테스트/로컬 실행 시 RAG 의존성 우회
    os.environ["ENABLE_RAG"] = "false"
    for key in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        os.environ.setdefault(key, "")
    config = AppConfig(
        enable_rag=False,
        neo4j_uri=None,
        neo4j_user=None,
        neo4j_password=None,
        _env_file=None,
    )
    generator = QAGenerator(config)
    sample_ocr = _load_default_ocr_text()
    pairs = generator.generate_qa(sample_ocr, query_count=4)
    generator.save_results(
        pairs,
        json_path="qa_result_4pairs.json",
        markdown_path="qa_result_4pairs.md",
    )
    LOGGER.info("Generated %d QA pairs", len(pairs))


def _should_autorun() -> bool:
    """Determine whether to run the example flow automatically."""
    return (
        __name__ == "__main__"
        or "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
    )


if _should_autorun():
    _run_example()
