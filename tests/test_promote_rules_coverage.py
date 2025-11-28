"""Tests for src/automation/promote_rules.py to improve coverage."""

from pathlib import Path


class TestHelperFunctions:
    """Test helper functions in promote_rules module."""

    def test_get_review_logs_dir(self):
        """Test get_review_logs_dir returns correct path."""
        from src.automation.promote_rules import get_review_logs_dir

        result = get_review_logs_dir()

        assert isinstance(result, Path)
        assert result.name == "review_logs"
        assert result.parent.name == "outputs"

    def test_get_output_dir(self):
        """Test get_output_dir returns correct path."""
        from src.automation.promote_rules import get_output_dir

        result = get_output_dir()

        assert isinstance(result, Path)
        assert result.name == "outputs"


class TestGetRecentLogFiles:
    """Test get_recent_log_files function."""

    def test_empty_directory(self, tmp_path):
        """Test with empty directory."""
        from src.automation.promote_rules import get_recent_log_files

        result = get_recent_log_files(tmp_path, days=7)

        assert result == []

    def test_nonexistent_directory(self, tmp_path):
        """Test with non-existent directory."""
        from src.automation.promote_rules import get_recent_log_files

        nonexistent = tmp_path / "nonexistent"
        result = get_recent_log_files(nonexistent, days=7)

        assert result == []

    def test_finds_recent_files(self, tmp_path):
        """Test finds recent JSONL files."""
        from src.automation.promote_rules import get_recent_log_files

        # Create a recent file
        recent_file = tmp_path / "recent.jsonl"
        recent_file.write_text('{"test": true}')

        result = get_recent_log_files(tmp_path, days=7)

        assert len(result) == 1
        assert result[0] == recent_file


class TestIsMeaningfulComment:
    """Test _is_meaningful_comment function."""

    def test_none_value(self):
        """Test None returns False."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment(None) is False

    def test_empty_string(self):
        """Test empty string returns False."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment("") is False

    def test_whitespace_only(self):
        """Test whitespace-only string returns False."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment("   ") is False

    def test_too_short(self):
        """Test short string returns False."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment("ok") is False

    def test_meaningful_comment(self):
        """Test meaningful comment returns True."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment("날짜 형식을 수정해주세요") is True

    def test_non_string_value(self):
        """Test non-string value is converted."""
        from src.automation.promote_rules import _is_meaningful_comment

        assert _is_meaningful_comment(12345678) is True


class TestExtractCommentsFromFiles:
    """Test extract_comments_from_files function."""

    def test_empty_file_list(self):
        """Test with empty file list."""
        from src.automation.promote_rules import extract_comments_from_files

        result = extract_comments_from_files([])

        assert result == []

    def test_extracts_comments(self, tmp_path):
        """Test extracts inspector_comment and edit_request_used."""
        from src.automation.promote_rules import extract_comments_from_files

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"inspector_comment": "날짜 형식이 잘못되었습니다"}\n'
            '{"edit_request_used": "문장을 더 간결하게 수정해주세요"}\n'
        )

        result = extract_comments_from_files([log_file])

        assert len(result) == 2
        assert "날짜 형식이 잘못되었습니다" in result
        assert "문장을 더 간결하게 수정해주세요" in result

    def test_skips_empty_comments(self, tmp_path):
        """Test skips empty or short comments."""
        from src.automation.promote_rules import extract_comments_from_files

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"inspector_comment": ""}\n'
            '{"inspector_comment": "ok"}\n'
            '{"inspector_comment": "이것은 의미있는 코멘트입니다"}\n'
        )

        result = extract_comments_from_files([log_file])

        assert len(result) == 1
        assert "이것은 의미있는 코멘트입니다" in result

    def test_handles_invalid_json(self, tmp_path):
        """Test handles invalid JSON gracefully."""
        from src.automation.promote_rules import extract_comments_from_files

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            'invalid json line\n{"inspector_comment": "유효한 코멘트입니다"}\n'
        )

        result = extract_comments_from_files([log_file])

        assert len(result) == 1
        assert "유효한 코멘트입니다" in result

    def test_handles_file_error(self, tmp_path):
        """Test handles file read errors gracefully."""
        from src.automation.promote_rules import extract_comments_from_files

        nonexistent = tmp_path / "nonexistent.jsonl"

        result = extract_comments_from_files([nonexistent])

        assert result == []

    def test_deduplicates_comments(self, tmp_path):
        """Test removes duplicate comments."""
        from src.automation.promote_rules import extract_comments_from_files

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"inspector_comment": "중복된 코멘트입니다"}\n'
            '{"inspector_comment": "중복된 코멘트입니다"}\n'
        )

        result = extract_comments_from_files([log_file])

        assert len(result) == 1


class TestBuildLLMPrompt:
    """Test build_llm_prompt function."""

    def test_build_prompt(self):
        """Test builds correct prompt."""
        from src.automation.promote_rules import build_llm_prompt

        comments = ["코멘트 1", "코멘트 2"]

        result = build_llm_prompt(comments)

        assert "코멘트 1" in result
        assert "코멘트 2" in result
        assert "JSON 배열" in result


class TestParseLLMResponse:
    """Test parse_llm_response function."""

    def test_parse_valid_response(self):
        """Test parses valid JSON response."""
        from src.automation.promote_rules import parse_llm_response

        response = """```json
[
  {
    "rule": "날짜 형식 통일",
    "type_hint": "date",
    "constraint": "YYYY-MM-DD 형식",
    "before": "2024/01/15",
    "after": "2024-01-15"
  }
]
```"""

        result = parse_llm_response(response)

        assert len(result) == 1
        assert result[0]["rule"] == "날짜 형식 통일"
        assert result[0]["type_hint"] == "date"
        assert result[0]["constraint"] == "YYYY-MM-DD 형식"

    def test_parse_without_code_block(self):
        """Test parses JSON without markdown code block."""
        from src.automation.promote_rules import parse_llm_response

        response = """[{"rule": "테스트 규칙", "type_hint": "string"}]"""

        result = parse_llm_response(response)

        assert len(result) == 1
        assert result[0]["rule"] == "테스트 규칙"

    def test_parse_invalid_json(self):
        """Test returns empty list for invalid JSON."""
        from src.automation.promote_rules import parse_llm_response

        response = "invalid json response"

        result = parse_llm_response(response)

        assert result == []

    def test_parse_missing_required_fields(self):
        """Test skips items missing required fields."""
        from src.automation.promote_rules import parse_llm_response

        response = """[
          {"rule": "규칙만 있음"},
          {"rule": "완전한 규칙", "type_hint": "string"}
        ]"""

        result = parse_llm_response(response)

        assert len(result) == 1
        assert result[0]["rule"] == "완전한 규칙"

    def test_parse_non_list_response(self):
        """Test returns empty list for non-list JSON."""
        from src.automation.promote_rules import parse_llm_response

        response = '{"single": "object"}'

        result = parse_llm_response(response)

        assert result == []

    def test_parse_no_brackets(self):
        """Test returns empty list when no brackets found."""
        from src.automation.promote_rules import parse_llm_response

        response = "some text without brackets"

        result = parse_llm_response(response)

        assert result == []


class TestPrintSummary:
    """Test print_summary function."""

    def test_print_empty_rules(self, capsys):
        """Test prints message for empty rules."""
        from src.automation.promote_rules import print_summary

        print_summary([])

        captured = capsys.readouterr()
        assert "규칙 후보 없음" in captured.out

    def test_print_rules_summary(self, capsys):
        """Test prints rules summary."""
        from src.automation.promote_rules import print_summary

        rules = [
            {
                "rule": "날짜 형식 통일",
                "type_hint": "date",
                "constraint": "ISO 8601",
                "best_practice": "UTC 기준",
                "before": "2024/01/15",
                "after": "2024-01-15",
            }
        ]

        print_summary(rules)

        captured = capsys.readouterr()
        assert "날짜 형식 통일" in captured.out
        assert "date" in captured.out
        assert "ISO 8601" in captured.out


class TestPromotedRuleTypedDict:
    """Test PromotedRule TypedDict."""

    def test_promoted_rule_required_fields(self):
        """Test PromotedRule with required fields."""
        from src.automation.promote_rules import PromotedRule

        rule: PromotedRule = {
            "rule": "테스트 규칙",
            "type_hint": "string",
        }
        assert rule["rule"] == "테스트 규칙"
        assert rule["type_hint"] == "string"

    def test_promoted_rule_all_fields(self):
        """Test PromotedRule with all fields."""
        from src.automation.promote_rules import PromotedRule

        rule: PromotedRule = {
            "rule": "테스트 규칙",
            "type_hint": "string",
            "constraint": "제약조건",
            "best_practice": "권고사항",
            "before": "수정전",
            "after": "수정후",
        }
        assert rule["constraint"] == "제약조건"
        assert rule["best_practice"] == "권고사항"
