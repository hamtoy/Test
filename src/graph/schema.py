"""그래프 스키마 정의."""

from __future__ import annotations

from typing import Any

# 질의 유형 정의
QUERY_TYPES: list[dict[str, Any]] = [
    {
        "name": "explanation",
        "korean": "전체 설명문",
        "limit": 1,
        "requires_reconstruction": True,
    },
    {
        "name": "summary",
        "korean": "전체 요약문",
        "limit": 1,
        "requires_reconstruction": True,
    },
    {
        "name": "target",
        "korean": "이미지 내 타겟",
        "limit": None,
        "requires_reconstruction": False,
    },
    {
        "name": "reasoning",
        "korean": "추론 질의",
        "limit": 1,
        "requires_reconstruction": False,
    },
]

# 제약 조건 정의
CONSTRAINTS: list[dict[str, Any]] = [
    {
        "id": "session_turns",
        "description": "세션당 3-4턴만 허용",
        "type": "count",
        "min": 3,
        "max": 4,
        "category": "query",
    },
    {
        "id": "explanation_summary_limit",
        "description": "설명문/요약문 중 하나만 포함",
        "type": "exclusivity",
        "exception": "4턴 세션에서만 둘 다 허용",
        "category": "query",
    },
    {
        "id": "calculation_limit",
        "description": "계산 요청 질의 1회 제한",
        "type": "count",
        "max": 1,
        "category": "query",
    },
    {
        "id": "table_chart_prohibition",
        "description": "표/그래프 참조 금지",
        "type": "prohibition",
        "pattern": r"(표|그래프)(에 따르면|에서)",
        "category": "answer",
    },
]

# 템플릿 정의
TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tmpl_explanation",
        "name": "explanation_system",
        "enforces": ["session_turns", "table_chart_prohibition"],
        "includes": [],
    },
    {
        "id": "tmpl_summary",
        "name": "summary_system",
        "enforces": [
            "session_turns",
            "table_chart_prohibition",
            "explanation_summary_limit",
        ],
        "includes": [],
    },
    {
        "id": "tmpl_target",
        "name": "target_user",
        "enforces": ["calculation_limit", "table_chart_prohibition"],
        "includes": [],
    },
    {
        "id": "tmpl_reasoning",
        "name": "reasoning_system",
        "enforces": ["session_turns", "table_chart_prohibition"],
        "includes": [],
    },
]

# 에러 패턴 정의
ERROR_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "err_table_ref",
        "pattern": "(표|그래프)(에 따르면|에서)",
        "description": "표/그래프 참조",
    },
    {
        "id": "err_definition",
        "pattern": "용어\\s*(정의|설명)",
        "description": "용어 정의 질문",
    },
    {
        "id": "err_full_image",
        "pattern": "전체\\s*이미지\\s*(설명|요약)",
        "description": "전체 이미지 설명/요약",
    },
    {
        "id": "err_time_reference",
        "pattern": (
            "(.?)(지난달|전일|지난주|주말|최근|올해|내년|연초|"
            "last month|yesterday|last week|recently|this year|next year|earlier this year)"
        ),
        "description": "시의성 표현은 보고서 기준 시점 명시 필요",
    },
]

# 모범 사례 정의
BEST_PRACTICES: list[dict[str, Any]] = [
    {
        "id": "bp_explanation",
        "text": "전체 본문을 재구성하되 고유명/숫자 그대로 유지",
        "applies_to": "explanation",
    },
    {
        "id": "bp_summary",
        "text": "설명의 20-30% 길이로 핵심만 요약",
        "applies_to": "summary",
    },
    {
        "id": "bp_reasoning",
        "text": "명시되지 않은 전망을 근거 기반으로 묻기",
        "applies_to": "reasoning",
    },
    {
        "id": "bp_target",
        "text": "중복 위치 피하고 단일 명확한 타겟 질문",
        "applies_to": "target",
    },
]
