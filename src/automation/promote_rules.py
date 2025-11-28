"""규칙 승격(Promote Rules) 자동화 스크립트.

이 스크립트는 최근 7일간의 검수 로그를 분석하여 자주 등장하는 검수 패턴을
규칙(rule) 형태로 추출하고 군집화/추상화합니다.

주요 기능:
1. data/outputs/review_logs/*.jsonl에서 최근 7일간 로그 파일 읽기
2. inspector_comment, edit_request_used 필드 추출 및 중복 제거
3. GeminiModelClient를 활용한 LLM 프롬프트로 패턴 군집화
4. 결과를 JSON 파일로 저장

사용법:
    # CLI에서 실행
    $ python -m src.automation.promote_rules

    # 함수로 호출
    from src.automation.promote_rules import run_promote_rules
    result = run_promote_rules()

출력:
    data/outputs/promoted_suggestions_{YYYYMMDD}.json

출력 JSON 스키마:
    [
        {
            "rule": "규칙 설명",
            "type_hint": "적용 타입 (예: string, number)",
            "constraint": "제약 조건 (optional)",
            "best_practice": "베스트 프랙티스 (optional)",
            "before": "수정 전 예시 (optional)",
            "after": "수정 후 예시 (optional)"
        },
        ...
    ]
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

# GeminiModelClient 임포트 (LLM 호출용)
from src.llm.gemini import GeminiModelClient


class PromotedRule(TypedDict, total=False):
    """승격된 규칙의 타입 정의.

    Attributes:
        rule: 규칙 설명 (필수)
        type_hint: 적용 타입 힌트 (필수)
        constraint: 제약 조건 (선택)
        best_practice: 베스트 프랙티스 권고 (선택)
        before: 수정 전 예시 (선택)
        after: 수정 후 예시 (선택)
    """

    rule: str
    type_hint: str
    constraint: str
    best_practice: str
    before: str
    after: str


def get_review_logs_dir() -> Path:
    """리뷰 로그 디렉토리 경로 반환.

    Returns:
        Path: data/outputs/review_logs 디렉토리 경로
    """
    # 프로젝트 루트 기준으로 경로 설정
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "outputs" / "review_logs"


def get_output_dir() -> Path:
    """출력 디렉토리 경로 반환.

    Returns:
        Path: data/outputs 디렉토리 경로
    """
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "outputs"


def get_recent_log_files(log_dir: Path, days: int = 7) -> list[Path]:
    """최근 N일간의 로그 파일 목록을 반환.

    Args:
        log_dir: 로그 디렉토리 경로
        days: 조회할 일수 (기본값: 7)

    Returns:
        list[Path]: 최근 N일간의 .jsonl 파일 경로 목록
    """
    if not log_dir.exists():
        return []

    cutoff_time = datetime.now() - timedelta(days=days)
    result: list[Path] = []

    # .jsonl 파일 검색
    for pattern in ["*.jsonl", "**/*.jsonl"]:
        for file_path_str in glob.glob(str(log_dir / pattern), recursive=True):
            file_path = Path(file_path_str)
            if file_path.is_file():
                # 파일 수정 시간 확인
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime >= cutoff_time:
                    result.append(file_path)

    return sorted(set(result))  # 중복 제거 및 정렬


def extract_comments_from_files(file_paths: list[Path]) -> list[str]:
    """로그 파일들에서 inspector_comment, edit_request_used 필드 추출.

    각 JSONL 파일의 각 줄에서 해당 필드를 추출하고,
    빈 문자열이나 의미 없는 값은 건너뜁니다.

    Args:
        file_paths: JSONL 파일 경로 목록

    Returns:
        list[str]: 추출된 코멘트 문자열 리스트 (중복 제거됨)
    """
    comments: set[str] = set()

    for file_path in file_paths:
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)

                        # inspector_comment 추출
                        if isinstance(data, dict):
                            inspector_comment = data.get("inspector_comment", "")
                            if _is_meaningful_comment(inspector_comment):
                                comments.add(str(inspector_comment).strip())

                            # edit_request_used 추출
                            edit_request = data.get("edit_request_used", "")
                            if _is_meaningful_comment(edit_request):
                                comments.add(str(edit_request).strip())

                    except json.JSONDecodeError:
                        # 잘못된 JSON 라인은 건너뜀
                        continue
        except OSError:
            # 파일 읽기 실패는 건너뜀
            continue

    return list(comments)


def _is_meaningful_comment(value: Any) -> bool:
    """코멘트 값이 의미있는지 확인.

    빈 문자열, None, 공백만 있는 문자열 등은 의미없는 것으로 판단.

    Args:
        value: 확인할 값

    Returns:
        bool: 의미있는 코멘트면 True
    """
    if value is None:
        return False
    if not isinstance(value, str):
        value = str(value)
    stripped = value.strip()
    if not stripped:
        return False
    # 너무 짧은 코멘트 제외 (예: "ok", "y" 등)
    return len(stripped) >= 5


def build_llm_prompt(comments: list[str]) -> str:
    """LLM에 전달할 프롬프트 생성.

    Args:
        comments: 추출된 코멘트 리스트

    Returns:
        str: LLM 프롬프트 문자열
    """
    comments_text = "\n".join(f"- {c}" for c in comments[:100])  # 최대 100개로 제한

    prompt = f"""다음은 검수자가 남긴 코멘트와 수정 요청 목록입니다.
이 코멘트들을 분석하여 자주 등장하는 패턴을 군집화하고,
각 패턴을 규칙(rule) 형태로 추상화해 주세요.

[코멘트 목록]
{comments_text}

위 코멘트들을 분석하여, 다음 형식의 JSON 배열로 반환해 주세요.
각 항목은 다음 필드를 가집니다:
- rule (필수): 규칙에 대한 간결한 설명
- type_hint (필수): 이 규칙이 적용되는 타입 (예: "string", "number", "date", "object")
- constraint (선택): 구체적인 제약 조건
- best_practice (선택): 베스트 프랙티스 권고사항
- before (선택): 수정 전 예시
- after (선택): 수정 후 예시

JSON 배열만 반환하고, 다른 설명은 추가하지 마세요.

예시 출력:
[
  {{
    "rule": "날짜 형식을 YYYY-MM-DD로 통일",
    "type_hint": "date",
    "constraint": "ISO 8601 형식 준수",
    "best_practice": "모든 날짜 필드는 UTC 기준으로 저장",
    "before": "2024/01/15",
    "after": "2024-01-15"
  }},
  {{
    "rule": "문자열 앞뒤 공백 제거",
    "type_hint": "string",
    "constraint": "trim 필수",
    "best_practice": "입력 시점에 정규화 수행"
  }}
]
"""
    return prompt


def parse_llm_response(response_text: str) -> list[PromotedRule]:
    """LLM 응답에서 JSON 배열 파싱.

    Args:
        response_text: LLM 응답 문자열

    Returns:
        list[PromotedRule]: 파싱된 규칙 리스트
    """
    # 마크다운 코드 블록 제거
    text = response_text.strip()
    text = text.removeprefix("```json")
    text = text.removeprefix("```")
    text = text.removesuffix("```")
    text = text.strip()

    # JSON 배열 찾기
    start_idx = text.find("[")
    end_idx = text.rfind("]")

    if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
        return []

    json_str = text[start_idx : end_idx + 1]

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, list):
            return []

        result: list[PromotedRule] = []
        for item in parsed:
            if isinstance(item, dict) and "rule" in item and "type_hint" in item:
                rule_entry: PromotedRule = {
                    "rule": str(item.get("rule", "")),
                    "type_hint": str(item.get("type_hint", "")),
                }
                if "constraint" in item:
                    rule_entry["constraint"] = str(item["constraint"])
                if "best_practice" in item:
                    rule_entry["best_practice"] = str(item["best_practice"])
                if "before" in item:
                    rule_entry["before"] = str(item["before"])
                if "after" in item:
                    rule_entry["after"] = str(item["after"])
                result.append(rule_entry)

        return result
    except json.JSONDecodeError:
        return []


def run_promote_rules(days: int = 7) -> list[PromotedRule]:
    """규칙 승격 메인 함수.

    최근 N일간의 검수 로그를 분석하여 규칙을 추출하고 저장합니다.

    Args:
        days: 조회할 일수 (기본값: 7)

    Returns:
        list[PromotedRule]: 추출된 규칙 리스트

    Raises:
        EnvironmentError: GEMINI_API_KEY가 설정되지 않은 경우
    """
    # 1. 로그 파일 경로 조회
    log_dir = get_review_logs_dir()
    log_files = get_recent_log_files(log_dir, days=days)

    if not log_files:
        print(f"최근 {days}일간의 로그 파일이 없습니다: {log_dir}")
        return []

    print(f"발견된 로그 파일: {len(log_files)}개")

    # 2. 코멘트 추출
    comments = extract_comments_from_files(log_files)

    if not comments:
        print("추출된 코멘트가 없습니다.")
        return []

    print(f"추출된 고유 코멘트: {len(comments)}개")

    # 3. LLM 호출
    try:
        client = GeminiModelClient()
    except EnvironmentError as e:
        print(f"LLM 클라이언트 초기화 실패: {e}")
        raise

    prompt = build_llm_prompt(comments)
    print("LLM에 패턴 분석 요청 중...")

    response = client.generate(prompt, temperature=0.3)

    if response.startswith("[생성 실패"):
        print(f"LLM 호출 실패: {response}")
        return []

    # 4. 응답 파싱
    rules = parse_llm_response(response)

    if not rules:
        print("규칙 파싱에 실패했습니다.")
        print(f"원본 응답: {response[:500]}")
        return []

    print(f"추출된 규칙: {len(rules)}개")

    # 5. 결과 저장
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    output_file = output_dir / f"promoted_suggestions_{today}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"결과 저장 완료: {output_file}")

    return rules


def print_summary(rules: list[PromotedRule]) -> None:
    """규칙 요약 출력.

    Args:
        rules: 출력할 규칙 리스트
    """
    if not rules:
        print("\n=== 규칙 후보 없음 ===")
        return

    print(f"\n=== 규칙 후보 요약 ({len(rules)}개) ===")
    print("-" * 50)

    for i, rule in enumerate(rules, 1):
        print(f"\n[{i}] {rule.get('rule', 'N/A')}")
        print(f"    타입: {rule.get('type_hint', 'N/A')}")

        if "constraint" in rule:
            print(f"    제약: {rule['constraint']}")
        if "best_practice" in rule:
            print(f"    권고: {rule['best_practice']}")
        if "before" in rule and "after" in rule:
            print(f"    예시: {rule['before']} → {rule['after']}")

    print("\n" + "-" * 50)


def main() -> None:
    """CLI 엔트리포인트.

    사용법:
        python -m src.automation.promote_rules
    """
    print("=" * 50)
    print("규칙 승격(Promote Rules) 자동화 스크립트")
    print("=" * 50)

    try:
        rules = run_promote_rules(days=7)
        print_summary(rules)

        if rules:
            sys.exit(0)
        else:
            sys.exit(1)

    except EnvironmentError as e:
        print(f"\n오류: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
        sys.exit(130)


if __name__ == "__main__":
    main()
