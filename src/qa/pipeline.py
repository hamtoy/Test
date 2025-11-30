from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.qa.rag_system import QAKnowledgeGraph
from src.processing.template_generator import DynamicTemplateGenerator
from scripts.build_session import SessionContext, build_session
from checks.validate_session import validate_turns
from checks.detect_forbidden_patterns import find_violations

load_dotenv()


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class IntegratedQAPipeline:
    """Graph-backed QA session builder and validator."""

    def __init__(self) -> None:
        self.neo4j_uri = require_env("NEO4J_URI")
        self.neo4j_user = require_env("NEO4J_USER")
        self.neo4j_password = require_env("NEO4J_PASSWORD")

        self.kg = QAKnowledgeGraph()
        self.template_gen = DynamicTemplateGenerator(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

    def create_session(self, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        """그래프 기반 컨텍스트로 세션을 생성하고 검증합니다.

        Args:
            image_meta: 이미지/텍스트 메타데이터 (text_density, has_table_chart 등 포함).

        Returns:
            dict: {"turns": 세션 턴 딕셔너리 리스트, "context": 세션 컨텍스트}

        Raises:
            ValueError: 금지 패턴 검출 또는 세션 검증 실패 시.
        """
        ctx_data = self._build_session_context(image_meta)
        ctx = SessionContext(**ctx_data)

        # 세션 빌드 (calc/포커스/금지 패턴 포함)
        turns = build_session(ctx, validate=True)
        turns_list: List[Dict[str, Any]] = [t.__dict__ for t in turns]
        session: Dict[str, Any] = {"turns": turns_list, "context": ctx_data}

        # 추가: 각 턴에 렌더된 프롬프트를 template generator로 재구성 (Rule/Constraint 주입)
        for turn in turns_list:
            turn["prompt"] = self.template_gen.generate_prompt_for_query_type(
                turn["type"], ctx_data
            )

        # 렌더링 후 금지 패턴 재검사
        post_violations = [
            f"turn {idx} ({turn['type']}): {v['type']} -> {v['match']}"
            for idx, turn in enumerate(turns_list, 1)
            for v in find_violations(turn["prompt"])
        ]
        if post_violations:
            raise ValueError(f"렌더링 후 금지 패턴 검출: {post_violations}")

        # 검증
        result = validate_turns(turns, ctx)
        if not result["ok"]:
            raise ValueError(f"세션 검증 실패: {result['issues']}")

        return session

    def _build_session_context(self, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        """SessionContext 스키마에 맞게 메타데이터를 변환하고 기본값을 채웁니다.

        Args:
            image_meta: 이미지 메타데이터 딕셔너리.

        Returns:
            SessionContext 초기화에 사용 가능한 딕셔너리.
        """
        density = image_meta.get("text_density", "high")
        if isinstance(density, (int, float)):
            density = (
                "high" if density >= 0.7 else "medium" if density >= 0.4 else "low"
            )

        return {
            "image_path": image_meta.get("image_path", "N/A"),
            "language_hint": image_meta.get("language_hint", "ko"),
            "text_density": density,
            "has_table_chart": bool(image_meta.get("has_table_chart", False)),
            "session_turns": int(image_meta.get("session_turns", 4)),
            "must_include_reasoning": bool(
                image_meta.get("must_include_reasoning", True)
            ),
            "used_calc_query_count": int(image_meta.get("used_calc_query_count", 0)),
            "prior_focus_summary": image_meta.get(
                "prior_focus_summary", "N/A (first turn)"
            ),
            "candidate_focus": image_meta.get(
                "candidate_focus", "전체 본문을 골고루 커버"
            ),
            "focus_history": image_meta.get("focus_history", []),
        }

    def validate_output(self, query_type: str, output: str) -> Dict[str, Any]:
        """출력 검증: 금지 패턴, 에러 패턴, 관련 규칙 기반 검사.
        """
        violations: List[str] = [
            f"forbidden_pattern:{v['type']}" for v in find_violations(output)
        ]

        # ErrorPattern 노드 기반 정규식 검사
        ep_cypher = """
        MATCH (ep:ErrorPattern)
        RETURN ep.pattern AS pattern, ep.description AS desc
        """
        with self.template_gen.driver.session() as session:
            for record in session.run(ep_cypher):
                pat = record["pattern"]
                if re.search(pat, output, flags=re.IGNORECASE):
                    violations.append(f"error_pattern:{record['desc']}")

        # 관련 규칙 조회 (Rule->QueryType 매핑)
        rule_cypher = """
        MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
        RETURN r.text AS text
        """
        missing_rules = []
        with self.template_gen.driver.session() as session:
            for record in session.run(rule_cypher, qt=query_type):
                text = record["text"]
                if text and text[:30] not in output:
                    # 단순 힌트: 규칙 단편이 출력에 반영되지 않은 경우
                    missing_rules.append(text[:30])

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "missing_rules_hint": missing_rules[:3],
        }

    def close(self) -> None:
        with suppress(Exception):
            self.kg.close()
        with suppress(Exception):
            self.template_gen.close()


def run_integrated_pipeline(meta_path: Path) -> Dict[str, Any]:
    """파일에서 메타데이터를 읽어 통합 파이프라인을 실행합니다.

    Args:
        meta_path: 이미지 메타데이터 JSON 경로

    Returns:
        세션 딕셔너리 {"turns": [...], "context": {...}}
    """
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pipeline = IntegratedQAPipeline()
    try:
        session = pipeline.create_session(meta)
        return session
    finally:
        pipeline.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    default_meta = root / "examples" / "session_input.json"
    session = run_integrated_pipeline(default_meta)
    print("📋 생성된 세션:")
    for i, turn in enumerate(session["turns"], 1):
        print(f"\n{i}. {turn['type']}")
        print(f"   프롬프트 길이: {len(turn['prompt'])} chars")
