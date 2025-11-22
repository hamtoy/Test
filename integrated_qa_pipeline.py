from __future__ import annotations

import os
import sys
import re
from typing import Dict, List, Any

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from qa_rag_system import QAKnowledgeGraph  # noqa: E402
from dynamic_template_generator import DynamicTemplateGenerator  # noqa: E402
from scripts.build_session import SessionContext, build_session  # noqa: E402
from checks.validate_session import validate_turns  # noqa: E402
from checks.detect_forbidden_patterns import find_violations  # noqa: E402


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class IntegratedQAPipeline:
    def __init__(self):
        self.neo4j_uri = require_env("NEO4J_URI")
        self.neo4j_user = require_env("NEO4J_USER")
        self.neo4j_password = require_env("NEO4J_PASSWORD")

        self.kg = QAKnowledgeGraph()
        self.template_gen = DynamicTemplateGenerator(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

    def create_session(self, image_meta: dict) -> Dict[str, Any]:
        """
        그래프 기반 컨텍스트를 주입해 세션 생성 후 최신 validator로 검증.
        """
        ctx_data = self._build_session_context(image_meta)
        ctx = SessionContext(**ctx_data)

        # 세션 빌드 (calc/포커스/금지 패턴 포함)
        turns = build_session(ctx, validate=True)
        session = {"turns": [t.__dict__ for t in turns], "context": ctx_data}

        # 추가: 각 턴에 렌더된 프롬프트를 template generator로 재구성 (Rule/Constraint 주입)
        for turn in session["turns"]:
            turn["prompt"] = self.template_gen.generate_prompt_for_query_type(
                turn["type"], ctx_data
            )

        # 렌더링 후 금지 패턴 재검사
        post_violations = []
        for idx, turn in enumerate(session["turns"], 1):
            for v in find_violations(turn["prompt"]):
                post_violations.append(
                    f"turn {idx} ({turn['type']}): {v['type']} -> {v['match']}"
                )
        if post_violations:
            raise ValueError(f"렌더링 후 금지 패턴 검출: {post_violations}")

        # 검증
        result = validate_turns(turns, ctx)
        if not result["ok"]:
            raise ValueError(f"세션 검증 실패: {result['issues']}")

        return session

    def _build_session_context(self, image_meta: dict) -> dict:
        """
        SessionContext에서 요구하는 필드로 변환/기본값 설정.
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
        """
        출력 검증: 금지 패턴, 에러 패턴, 관련 규칙 기반 검사.
        """
        violations: List[str] = []

        # 금지 패턴 (정규식)
        for v in find_violations(output):
            violations.append(f"forbidden_pattern:{v['type']}")

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

    def close(self):
        try:
            self.kg.close()
        except Exception:
            pass
        try:
            self.template_gen.close()
        except Exception:
            pass


if __name__ == "__main__":
    pipeline = IntegratedQAPipeline()

    image_meta = {
        "image_path": "report.png",
        "has_table_chart": True,
        "text_density": 0.85,
        "language_hint": "ko",
        "session_turns": 4,
        "must_include_reasoning": True,
    }

    session = pipeline.create_session(image_meta)
    print("📋 생성된 세션:")
    for i, turn in enumerate(session["turns"], 1):
        print(f"\n{i}. {turn['type']}")
        print(f"   프롬프트 길이: {len(turn['prompt'])} chars")

    pipeline.close()
