from __future__ import annotations

from typing import Any, Dict, List

from src.llm.gemini import GeminiModelClient
from src.qa.rag_system import QAKnowledgeGraph


class SelfCorrectingQAChain:
    """Gemini 기반 자기 교정형 QA 체인.

    초안 → 비평 → 수정 → 최종 검증을 반복합니다.
    """

    def __init__(self, kg: QAKnowledgeGraph, llm: GeminiModelClient | None = None):
        """Initialize the self-correcting QA chain.

        Args:
            kg: QAKnowledgeGraph instance for graph queries.
            llm: Optional Gemini model client.
        """
        self.kg = kg
        self.llm = llm or GeminiModelClient()

    def generate_with_self_correction(
        self, query_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """규칙을 가져와 자기 교정 프로세스를 실행합니다."""
        rules = self._get_rules_text(query_type)
        attempts = 0
        max_retries = 3
        last_result: Dict[str, str] = {}

        while attempts < max_retries:
            draft = self._draft(query_type, context, rules)
            critique = self._critique(draft, rules)
            corrected = self._correct(draft, critique, rules)
            final_validation = self._final_validate(corrected, rules)

            last_result = {
                "draft": draft,
                "critique": critique,
                "corrected": corrected,
                "final_validation": final_validation,
            }
            attempts += 1

            if "yes" in final_validation.lower():
                break

        return {
            "output": last_result.get("corrected", ""),
            "iterations": attempts,
            "validation": last_result.get("final_validation", ""),
        }

    def _get_rules_text(self, query_type: str) -> str:
        rules: List[Dict[str, str]] = self.kg.get_constraints_for_query_type(query_type)
        rule_lines = []
        for r in rules:
            desc = r.get("description") or r.get("id") or ""
            rule_lines.append(f"- {desc}")
        return "\n".join(rule_lines) or "(규칙 없음)"

    def _draft(self, query_type: str, context: Dict[str, Any], rules: str) -> str:
        prompt = f"""다음 규칙을 준수하여 한국어로 답변을 생성하세요.

[질의 유형]: {query_type}

[규칙]
{rules}

[컨텍스트]
{context}

반드시 한국어로 출력하세요:"""
        return self.llm.generate(prompt, role="draft")

    def _critique(self, draft: str, rules: str) -> str:
        prompt = f"""Review this draft against the rules:

Draft:
{draft}

Rules:
{rules}

List ALL violations and issues:"""
        return self.llm.generate(prompt, role="critique")

    def _correct(self, draft: str, critique: str, rules: str) -> str:
        prompt = f"""Original draft:
{draft}

Issues found:
{critique}

Rules:
{rules}

Generate CORRECTED version:"""
        return self.llm.generate(prompt, role="correct")

    def _final_validate(self, corrected: str, rules: str) -> str:
        prompt = f"""Final check:

Output:
{corrected}

Rules:
{rules}

Is this perfect? (yes/no and explain):"""
        return self.llm.generate(prompt, role="validator")
