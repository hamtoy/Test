from scripts.build_session import SessionContext, build_session
from checks.validate_session import validate_turns
from checks.detect_forbidden_patterns import find_violations
import pytest


def test_session_validation_pass() -> None:
    ctx = SessionContext(
        image_path="images/sample_korean_report.png",
        language_hint="ko",
        text_density="high",
        has_table_chart=True,
        session_turns=4,
        must_include_reasoning=True,
        used_calc_query_count=0,
        prior_focus_summary="N/A (first turn)",
        candidate_focus="주요 수치",
    )
    turns = build_session(ctx)
    result = validate_turns(turns, ctx)
    assert result["ok"] is True
    assert result["issues"] == []


def test_session_turn_count_invalid() -> None:
    ctx = SessionContext(
        image_path="images/sample_korean_report.png",
        language_hint="ko",
        text_density="high",
        has_table_chart=False,
        session_turns=5,  # invalid
        must_include_reasoning=False,
    )
    with pytest.raises(ValueError):
        build_session(ctx)


def test_forbidden_pattern_detection() -> None:
    text = "표에서 보이듯 성장했습니다."
    violations = find_violations(text)
    assert violations
    assert any(v["type"] == "표참조" for v in violations)


def test_calc_limit_enforced() -> None:
    # ctx already reports calc count 2, total > 1 should fail
    ctx = SessionContext(
        image_path="images/sample_korean_report.png",
        language_hint="ko",
        text_density="high",
        has_table_chart=False,
        session_turns=3,
        must_include_reasoning=False,
        used_calc_query_count=2,
    )
    turns = build_session(ctx)
    result = validate_turns(turns, ctx)
    assert result["ok"] is False
    assert any("calculation requests exceeded" in issue for issue in result["issues"])
