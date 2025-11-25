"""그래프 연결을 위한 매핑 데이터."""

from __future__ import annotations

# 제약-키워드 매핑
CONSTRAINT_KEYWORDS: dict[str, list[str]] = {
    "session_turns": ["3-4", "3턴", "4턴", "턴만", "3~4", "turn limit"],
    "explanation_summary_limit": [
        "설명문/요약문",
        "둘 다",
        "동시",
        "설명과 요약",
        "full image 설명",
        "전체 이미지 요약",
    ],
    "calculation_limit": [
        "계산",
        "연산",
        "계산 요청",
        "수식",
        "sum",
        "average",
        "평균값",
    ],
    "table_chart_prohibition": [
        "표",
        "그래프",
        "차트",
        "테이블",
        "table",
        "chart",
        "graph",
        "표 참고",
        "그래프 참고",
    ],
}

# QueryType-키워드 매핑
QUERY_TYPE_KEYWORDS: dict[str, list[str]] = {
    "explanation": ["전체 설명", "설명문", "full explanation", "본문 전체"],
    "summary": ["요약", "summary", "짧게"],
    "target": ["질문", "타겟", "target", "단일 항목"],
    "reasoning": [
        "추론",
        "전망",
        "예측",
        "분석",
        "금리",
        "물가",
        "심리",
        "수요",
        "공급",
        "rate",
        "inflation",
        "outlook",
    ],
}

# 예시-규칙 수동 매핑 (sim: 유사도 기준)
EXAMPLE_RULE_MAPPINGS: dict[str, str] = {
    "example_45d38ada918d23b7": "rule_45d38ada918d23b7",  # sim: 0.900
    "example_cf76634755769349": "rule_cf76634755769349",  # sim: 0.900
    "example_6d8d778d07679551": "rule_74fb853e8344cdae",  # sim: 0.264
    "example_3a822c5a7cb6febe": "rule_064a2e85eab0037a",  # sim: 0.219
    "example_4501bbd1a0ac6eeb": "rule_74fb853e8344cdae",  # sim: 0.217
    "example_6beb76f2c037af0a": "rule_064a2e85eab0037a",  # sim: 0.211
    "example_cc7329fc50d5c9c0": "rule_064a2e85eab0037a",  # sim: 0.209
    "example_5c9030841bc1f28a": "rule_f1b66e7991427573",  # sim: 0.202
    "example_c2297ccab80815be": "rule_ed715984caa427d9",  # sim: 0.201
    "example_bac3f6c4e74538cf": "rule_83a25f83293421cb",  # sim: 0.196
    "example_b9254ad66c943c63": "rule_ed715984caa427d9",  # sim: 0.194
    "example_361d2e6907476754": "rule_74fb853e8344cdae",  # sim: 0.185
    "example_f4ff0a927af9dd75": "rule_68126c74e965fc95",  # sim: 0.185
    "example_e64ff39e4f5ccdae": "rule_68126c74e965fc95",  # sim: 0.185
    "example_73ec90483d94de4e": "rule_74fb853e8344cdae",  # sim: 0.178
    "example_fc3b6beb75c97d73": "rule_1ec1943f3b2ac695",  # sim: 0.173
    "example_aa3a1556c30d903c": "rule_83a25f83293421cb",  # sim: 0.170
    "example_c8604f69e5419197": "rule_c3ad6e856a5e4eac",  # sim: 0.167
    "example_3e6f027c10f3ce19": "rule_c377a77caae6c9fc",  # sim: 0.166
    "example_642e3b1bf4c9c1c6": "rule_74fb853e8344cdae",  # sim: 0.165
    "example_44d1648296e64007": "rule_1ec1943f3b2ac695",  # sim: 0.156
    "example_916d03c24e532d7f": "rule_b40a33c04b44a9f8",  # sim: 0.153
    "example_3fdbe917fdc8da83": "rule_064a2e85eab0037a",  # sim: 0.153
    "example_04c2e4f5f3b8d07a": "rule_1ec1943f3b2ac695",  # sim: 0.152
    "example_598798882c9382af": "rule_1ec1943f3b2ac695",  # sim: 0.152
    "example_c8117a599dc04a8a": "rule_3d37cba5ab431c3c",  # sim: 0.152
    "example_ee8012b86a054472": "rule_b40a33c04b44a9f8",  # sim: 0.151
}
