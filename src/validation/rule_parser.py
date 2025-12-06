"""CSV 기반 검증 규칙 파서.

- guide.csv: 기본 검증 규칙 (시의성, 문장 품질 등)
- qna.csv: 상세 검증 체크리스트
- patterns.yaml: 패턴 기반 검증 규칙
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)


class RuleCSVParser:
    """CSV 파일에서 검증 규칙을 자동 추출."""

    def __init__(
        self,
        guide_path: str | None = None,
        qna_path: str | None = None,
        patterns_path: str | None = None,
    ) -> None:
        """Initialize RuleCSVParser.

        Args:
            guide_path: guide.csv 경로
            qna_path: qna.csv 경로
            patterns_path: patterns.yaml 경로 (FORBIDDEN_PATTERNS, FORMATTING_PATTERNS)
        """
        self.guide_path = Path(guide_path) if guide_path else None
        self.qna_path = Path(qna_path) if qna_path else None
        self.patterns_path = Path(patterns_path) if patterns_path else None
        self._cache: Dict[str, Any] = {}

    def parse_guide_csv(self) -> Dict[str, Any]:
        """guide.csv 파싱 → 기본 검증 규칙 추출.

        Returns:
            {
                'temporal_expressions': ['현재', '최근', '이미지에서'],
                'sentence_rules': {'min': 3, 'max': 4},
                'formatting': {...}
            }
        """
        if "guide" in self._cache:
            return self._cache["guide"]  # type: ignore[no-any-return]

        rules: Dict[str, Any] = {
            "temporal_expressions": [],
            "sentence_rules": {},
            "formatting_rules": [],
            "structure_rules": [],
        }

        if not self.guide_path or not self.guide_path.exists():
            logger.warning("guide.csv not found at %s", self.guide_path)
            return rules

        try:
            with open(self.guide_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    content = row.get("내용", "")

                    # 시의성 표현 규칙
                    if (
                        "시의성 표현" in content
                        or "현재" in content
                        or "최근" in content
                    ):
                        rules["temporal_expressions"] = [
                            "현재",
                            "최근",
                            "올해",
                            "이미지에서",
                        ]

                    # 문장 수 규칙
                    if "3-4문장" in content or "문장 수" in content:
                        rules["sentence_rules"] = {"min": 3, "max": 4}

                    # 포맷팅 규칙
                    if "볼드체" in content or "강조" in content:
                        rules["formatting_rules"].append(
                            {"type": "bold_usage", "rule": content}
                        )

                    # 구조 규칙
                    if "소제목" in content or "목록형" in content:
                        rules["structure_rules"].append(
                            {"type": "structure", "rule": content}
                        )

            logger.info("Successfully parsed guide.csv with %d rule types", len(rules))

        except Exception as exc:  # noqa: BLE001
            logger.error("guide.csv 파싱 오류: %s", exc)

        self._cache["guide"] = rules
        return rules

    def parse_qna_csv(self) -> Dict[str, List[Dict[str, str]]]:
        """qna.csv 파싱 → 검증 체크리스트 추출.

        Returns:
            {
                'question_checklist': [
                    {'category': '1. 질의의 유용성...', 'rules': [...]}
                ],
                'answer_checklist': [...],
                'work_checklist': [...]
            }
        """
        if "qna" in self._cache:
            return self._cache["qna"]  # type: ignore[no-any-return]

        checklist: Dict[str, List[Dict[str, str]]] = {
            "question_checklist": [],
            "answer_checklist": [],
            "work_checklist": [],
        }

        if not self.qna_path or not self.qna_path.exists():
            logger.warning("qna.csv not found at %s", self.qna_path)
            return checklist

        try:
            with open(self.qna_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    middle_category = row.get("중분류", "")
                    subcategory = row.get("소분류", "")
                    content = row.get("내용", "")

                    item = {
                        "subcategory": subcategory,
                        "content": content,
                        "full_key": f"{middle_category}_{subcategory}",
                    }

                    if middle_category == "질의":
                        checklist["question_checklist"].append(item)
                    elif middle_category == "답변":
                        checklist["answer_checklist"].append(item)
                    elif middle_category == "작업 규칙":
                        checklist["work_checklist"].append(item)

            logger.info(
                "Successfully parsed qna.csv with %d checklist items",
                sum(len(v) for v in checklist.values()),
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("qna.csv 파싱 오류: %s", exc)

        self._cache["qna"] = checklist
        return checklist

    def parse_patterns_yaml(self) -> Dict[str, Dict[str, Any]]:
        """patterns.yaml 파싱 → 패턴 기반 검증 규칙.

        Returns:
            {
                'forbidden_patterns': {...},
                'formatting_patterns': {...}
            }
        """
        if "patterns" in self._cache:
            return self._cache["patterns"]  # type: ignore[no-any-return]

        patterns: Dict[str, Dict[str, Any]] = {
            "forbidden_patterns": {},
            "formatting_patterns": {},
        }

        if not self.patterns_path or not self.patterns_path.exists():
            logger.warning("patterns.yaml not found at %s", self.patterns_path)
            return patterns

        try:
            with open(self.patterns_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                patterns["forbidden_patterns"] = data.get("forbidden_patterns", {})
                patterns["formatting_patterns"] = data.get("formatting_patterns", {})

            logger.info("Successfully parsed patterns.yaml")

        except Exception as exc:  # noqa: BLE001
            logger.error("patterns.yaml 파싱 오류: %s", exc)

        self._cache["patterns"] = patterns
        return patterns

    def get_all_rules(self) -> Dict[str, Any]:
        """모든 규칙 통합 반환."""
        return {
            "guide_rules": self.parse_guide_csv(),
            "qna_checklist": self.parse_qna_csv(),
            "pattern_rules": self.parse_patterns_yaml(),
        }


class RuleManager:
    """규칙 캐싱 및 관리."""

    def __init__(self, parser: RuleCSVParser) -> None:
        """Initialize RuleManager.

        Args:
            parser: RuleCSVParser instance
        """
        self.parser = parser
        self.rules: Dict[str, Any] | None = None

    def load_rules(self) -> Dict[str, Any]:
        """규칙 로드 (초기 로드 또는 리로드)."""
        self.rules = self.parser.get_all_rules()
        logger.info("Rules loaded successfully")
        return self.rules

    def get_temporal_rules(self) -> List[str]:
        """시의성 표현 규칙 조회."""
        if not self.rules:
            self.load_rules()
        assert self.rules is not None
        guide_rules = self.rules.get("guide_rules", {})
        assert isinstance(guide_rules, dict)
        temporal = guide_rules.get("temporal_expressions", [])
        assert isinstance(temporal, list)
        return temporal

    def get_sentence_rules(self) -> Dict[str, int]:
        """문장 수 규칙 조회."""
        if not self.rules:
            self.load_rules()
        assert self.rules is not None
        guide_rules = self.rules.get("guide_rules", {})
        assert isinstance(guide_rules, dict)
        sentence_rules = guide_rules.get("sentence_rules", {})
        assert isinstance(sentence_rules, dict)
        return sentence_rules  # type: ignore[no-any-return]

    def get_question_checklist(self) -> List[Dict[str, str]]:
        """질의 체크리스트 조회."""
        if not self.rules:
            self.load_rules()
        assert self.rules is not None
        qna_checklist = self.rules.get("qna_checklist", {})
        assert isinstance(qna_checklist, dict)
        question_checklist = qna_checklist.get("question_checklist", [])
        assert isinstance(question_checklist, list)
        return question_checklist  # type: ignore[no-any-return]

    def get_answer_checklist(self) -> List[Dict[str, str]]:
        """답변 체크리스트 조회."""
        if not self.rules:
            self.load_rules()
        assert self.rules is not None
        qna_checklist = self.rules.get("qna_checklist", {})
        assert isinstance(qna_checklist, dict)
        answer_checklist = qna_checklist.get("answer_checklist", [])
        assert isinstance(answer_checklist, list)
        return answer_checklist  # type: ignore[no-any-return]
