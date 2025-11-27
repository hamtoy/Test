from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.agent import GeminiAgent
from src.config import AppConfig


@dataclass
class ExperimentCase:
    case_id: str
    ocr_text: str
    user_intent: Optional[str] = None


@dataclass
class TemplateVariant:
    tag: str
    override_dir: Optional[Path] = None
    description: str = ""


class PromptExperimentRunner:
    """
    Minimal prompt experiment runner.

    - Allows swapping template directories per variant.
    - Runs generate_query on a set of cases.
    - Writes JSONL records for downstream comparison.
    """

    def __init__(self, config: AppConfig, cases: Iterable[ExperimentCase]):
        self.config = config
        self.cases = list(cases)

    def _jinja_env_for_variant(self, variant: TemplateVariant) -> Environment:
        search_paths: List[str] = []
        if variant.override_dir:
            search_paths.append(str(variant.override_dir))
        search_paths.append(str(self.config.template_dir))
        return Environment(loader=FileSystemLoader(search_paths), autoescape=True)

    @staticmethod
    def _append_jsonl(path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def _run_generate_query_variant(
        self, variant: TemplateVariant, output_path: Path
    ) -> None:
        env = self._jinja_env_for_variant(variant)
        agent = GeminiAgent(self.config, jinja_env=env)

        for case in self.cases:
            record: dict[str, object] = {
                "variant": variant.tag,
                "variant_description": variant.description,
                "case_id": case.case_id,
                "user_intent": case.user_intent,
                "queries": [],
                "error": None,
            }
            try:
                queries = await agent.generate_query(case.ocr_text, case.user_intent)
                record["queries"] = queries
                record["error"] = None
            except Exception as exc:  # noqa: BLE001
                record["queries"] = []
                record["error"] = str(exc)
            self._append_jsonl(output_path, record)

    def run_generate_query_variants(
        self,
        variants: Iterable[TemplateVariant],
        output_path: Path = Path("data/experiments/prompt_results.jsonl"),
    ) -> None:
        """
        Run generate_query across variants and cases, writing results to JSONL.
        """

        async def _run_all():
            for variant in variants:
                await self._run_generate_query_variant(variant, output_path)

        asyncio.run(_run_all())


def example_usage() -> None:
    """
    Small example: define cases and variants, then execute.
    Requires a valid GEMINI_API_KEY in the environment.
    """
    # AppConfig pulls from environment; ignore call-arg type check for BaseSettings ctor.
    config = AppConfig()
    cases = [
        ExperimentCase(case_id="1", ocr_text="표가 많은 문서", user_intent="요약"),
        ExperimentCase(case_id="2", ocr_text="계약서 조항", user_intent="검토"),
    ]
    variants = [
        TemplateVariant(tag="baseline"),
        TemplateVariant(
            tag="rewrite_v2",
            override_dir=Path("templates_experimental/rewrite_v2"),
            description="Rewrite prompt tweaked for brevity",
        ),
    ]
    runner = PromptExperimentRunner(config, cases)
    runner.run_generate_query_variants(variants)


if __name__ == "__main__":
    example_usage()
