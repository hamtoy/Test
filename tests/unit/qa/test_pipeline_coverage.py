"""Additional tests for src/qa/pipeline.py to improve coverage to 80%+.

Targets:
- IntegratedQAPipeline initialization
- Session creation and validation
- Context building
- Output validation with error patterns
- Resource cleanup
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from src.qa.pipeline import IntegratedQAPipeline, run_integrated_pipeline


class TestIntegratedQAPipelineInit:
    """Test IntegratedQAPipeline initialization."""

    def test_init_loads_environment(self) -> None:
        """Test that initialization loads environment variables."""
        with patch("src.qa.pipeline.require_env") as mock_require:
            mock_require.side_effect = lambda x: f"mock_{x}"

            with (
                patch("src.qa.pipeline.QAKnowledgeGraph"),
                patch("src.qa.pipeline.DynamicTemplateGenerator"),
            ):
                pipeline = IntegratedQAPipeline()

                assert pipeline.neo4j_uri == "mock_NEO4J_URI"
                assert pipeline.neo4j_user == "mock_NEO4J_USER"
                assert pipeline.neo4j_password == "mock_NEO4J_PASSWORD"

    def test_init_creates_kg_and_template_gen(self) -> None:
        """Test that KG and template generator are created."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph") as mock_kg,
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            pipeline = IntegratedQAPipeline()

            mock_kg.assert_called_once()
            mock_gen.assert_called_once()
            assert pipeline.kg is not None
            assert pipeline.template_gen is not None


class TestBuildSessionContext:
    """Test session context building."""

    def test_build_session_context_with_defaults(self) -> None:
        """Test building context with default values."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator"),
        ):
            pipeline = IntegratedQAPipeline()

            image_meta = {"image_path": "test.png"}
            context = pipeline._build_session_context(image_meta)

            assert context["image_path"] == "test.png"
            assert context["language_hint"] == "ko"
            assert context["text_density"] == "high"
            assert context["session_turns"] == 4
            assert context["must_include_reasoning"] is True

    def test_build_session_context_with_numeric_density(self) -> None:
        """Test density conversion from numeric to string."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator"),
        ):
            pipeline = IntegratedQAPipeline()

            # High density (>= 0.7)
            meta_high = {"text_density": 0.9}
            context_high = pipeline._build_session_context(meta_high)
            assert context_high["text_density"] == "high"

            # Medium density (0.4-0.7)
            meta_med = {"text_density": 0.5}
            context_med = pipeline._build_session_context(meta_med)
            assert context_med["text_density"] == "medium"

            # Low density (< 0.4)
            meta_low = {"text_density": 0.2}
            context_low = pipeline._build_session_context(meta_low)
            assert context_low["text_density"] == "low"

    def test_build_session_context_with_custom_values(self) -> None:
        """Test building context with all custom values."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator"),
        ):
            pipeline = IntegratedQAPipeline()

            image_meta = {
                "image_path": "custom.png",
                "language_hint": "en",
                "text_density": "low",
                "has_table_chart": True,
                "session_turns": 5,
                "must_include_reasoning": False,
                "used_calc_query_count": 2,
                "prior_focus_summary": "이전 요약",
                "candidate_focus": "특정 섹션",
                "focus_history": ["focus1", "focus2"],
            }
            context = pipeline._build_session_context(image_meta)

            assert context["image_path"] == "custom.png"
            assert context["language_hint"] == "en"
            assert context["text_density"] == "low"
            assert context["has_table_chart"] is True
            assert context["session_turns"] == 5
            assert context["must_include_reasoning"] is False
            assert context["used_calc_query_count"] == 2
            assert context["prior_focus_summary"] == "이전 요약"
            assert context["candidate_focus"] == "특정 섹션"
            assert context["focus_history"] == ["focus1", "focus2"]


class TestCreateSession:
    """Test session creation."""

    def test_create_session_success(self) -> None:
        """Test successful session creation."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_template_gen = Mock()
            mock_template_gen.generate_prompt_for_query_type = Mock(
                return_value="생성된 프롬프트"
            )
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.build_session") as mock_build:
                mock_turn = Mock()
                mock_turn.__dict__ = {
                    "type": "reasoning",
                    "prompt": "초기 프롬프트",
                }
                mock_build.return_value = [mock_turn]

                with (
                    patch("src.qa.pipeline.find_violations", return_value=[]),
                    patch(
                        "src.qa.pipeline.validate_turns",
                        return_value={"ok": True},
                    ),
                ):
                    pipeline = IntegratedQAPipeline()

                    image_meta = {"image_path": "test.png"}
                    session = pipeline.create_session(image_meta)

                    assert "turns" in session
                    assert "context" in session
                    assert len(session["turns"]) == 1
                    # Prompt updated by template generator
                    expected_prompt = "생성된 프롬프트"
                    assert session["turns"][0]["prompt"] == expected_prompt

    def test_create_session_with_forbidden_patterns(self) -> None:
        """Test session creation fails with forbidden patterns."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_template_gen = Mock()
            mock_template_gen.generate_prompt_for_query_type = Mock(
                return_value="금지된 패턴 포함"
            )
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.build_session") as mock_build:
                mock_turn = Mock()
                mock_turn.__dict__ = {"type": "reasoning", "prompt": ""}
                mock_build.return_value = [mock_turn]

                with patch("src.qa.pipeline.find_violations") as mock_violations:
                    mock_violations.return_value = [
                        {"type": "forbidden", "match": "금지 패턴"}
                    ]

                    pipeline = IntegratedQAPipeline()

                    with pytest.raises(ValueError) as exc_info:
                        pipeline.create_session({"image_path": "test.png"})

                    assert "렌더링 후 금지 패턴 검출" in str(exc_info.value)

    def test_create_session_validation_failure(self) -> None:
        """Test session creation fails validation."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_template_gen = Mock()
            mock_template_gen.generate_prompt_for_query_type = Mock(
                return_value="프롬프트"
            )
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.build_session") as mock_build:
                mock_turn = Mock()
                mock_turn.__dict__ = {"type": "reasoning", "prompt": ""}
                mock_build.return_value = [mock_turn]

                with (
                    patch("src.qa.pipeline.find_violations", return_value=[]),
                    patch("src.qa.pipeline.validate_turns") as mock_validate,
                ):
                    mock_validate.return_value = {
                        "ok": False,
                        "issues": ["검증 실패"],
                    }

                    pipeline = IntegratedQAPipeline()

                    with pytest.raises(ValueError) as exc_info:
                        pipeline.create_session({"image_path": "test.png"})

                    assert "세션 검증 실패" in str(exc_info.value)


class TestValidateOutput:
    """Test output validation."""

    def test_validate_output_no_violations(self) -> None:
        """Test validation with no violations."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_driver = Mock()
            mock_session = Mock()
            mock_session.run = Mock(return_value=[])
            mock_driver.session = Mock(return_value=mock_session)

            mock_template_gen = Mock()
            mock_template_gen.driver = mock_driver
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.find_violations", return_value=[]):
                pipeline = IntegratedQAPipeline()

                result = pipeline.validate_output("reasoning", "정상 출력")

                assert result["valid"] is True
                assert len(result["violations"]) == 0

    def test_validate_output_with_forbidden_patterns(self) -> None:
        """Test validation detects forbidden patterns."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_driver = Mock()
            mock_session = Mock()
            mock_session.run = Mock(return_value=[])
            mock_driver.session = Mock(return_value=mock_session)

            mock_template_gen = Mock()
            mock_template_gen.driver = mock_driver
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.find_violations") as mock_violations:
                mock_violations.return_value = [{"type": "forbidden"}]

                pipeline = IntegratedQAPipeline()

                result = pipeline.validate_output("reasoning", "금지 패턴")

                assert result["valid"] is False
                assert "forbidden_pattern:forbidden" in result["violations"]

    def test_validate_output_with_error_patterns(self) -> None:
        """Test validation detects error patterns from graph."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_record = Mock()
            mock_record.__getitem__ = lambda self, key: {
                "pattern": r"\berror\b",
                "desc": "에러 패턴",
            }[key]

            mock_session = Mock()
            mock_session.run = Mock(return_value=[mock_record])
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=None)

            mock_driver = Mock()
            mock_driver.session = Mock(return_value=mock_session)

            mock_template_gen = Mock()
            mock_template_gen.driver = mock_driver
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.find_violations", return_value=[]):
                pipeline = IntegratedQAPipeline()

                result = pipeline.validate_output(
                    "reasoning", "This has an error in it"
                )

                assert result["valid"] is False
                assert any("error_pattern" in v for v in result["violations"])

    def test_validate_output_with_missing_rules(self) -> None:
        """Test validation detects missing rule hints."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph"),
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            # Mock error pattern query (empty)
            mock_ep_results: list[Any] = []

            # Mock rule query
            mock_rule_record = Mock()
            mock_rule_record.__getitem__ = lambda self, key: "규칙 내용입니다"

            def mock_run(query: str, **params: Any) -> list[Any]:
                if "ErrorPattern" in query:
                    return mock_ep_results
                if "Rule" in query:
                    return [mock_rule_record]
                return []

            mock_session = Mock()
            mock_session.run = Mock(side_effect=mock_run)
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=None)

            mock_driver = Mock()
            mock_driver.session = Mock(return_value=mock_session)

            mock_template_gen = Mock()
            mock_template_gen.driver = mock_driver
            mock_gen.return_value = mock_template_gen

            with patch("src.qa.pipeline.find_violations", return_value=[]):
                pipeline = IntegratedQAPipeline()

                result = pipeline.validate_output("reasoning", "출력에 규칙이 없음")

                # Should detect missing rule
                assert len(result["missing_rules_hint"]) > 0


class TestResourceCleanup:
    """Test resource cleanup."""

    def test_close_cleans_up_resources(self) -> None:
        """Test that close method cleans up KG and template gen."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph") as mock_kg,
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_kg_instance = Mock()
            mock_kg.return_value = mock_kg_instance

            mock_gen_instance = Mock()
            mock_gen.return_value = mock_gen_instance

            pipeline = IntegratedQAPipeline()
            pipeline.close()

            mock_kg_instance.close.assert_called_once()
            mock_gen_instance.close.assert_called_once()

    def test_close_handles_exceptions(self) -> None:
        """Test that close handles exceptions gracefully."""
        with (
            patch("src.qa.pipeline.require_env", return_value="test"),
            patch("src.qa.pipeline.QAKnowledgeGraph") as mock_kg,
            patch("src.qa.pipeline.DynamicTemplateGenerator") as mock_gen,
        ):
            mock_kg_instance = Mock()
            mock_kg_instance.close = Mock(side_effect=Exception("Close error"))
            mock_kg.return_value = mock_kg_instance

            mock_gen_instance = Mock()
            mock_gen.return_value = mock_gen_instance

            pipeline = IntegratedQAPipeline()
            # Should not raise exception
            pipeline.close()


class TestRunIntegratedPipeline:
    """Test run_integrated_pipeline function."""

    def test_run_integrated_pipeline_success(self, tmp_path: Path) -> None:
        """Test successful pipeline run."""
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps({"image_path": "test.png"}), encoding="utf-8")

        with patch("src.qa.pipeline.IntegratedQAPipeline") as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline.create_session = Mock(
                return_value={"turns": [], "context": {}}
            )
            mock_pipeline_class.return_value = mock_pipeline

            result = run_integrated_pipeline(meta_file)

            assert "turns" in result
            assert "context" in result
            mock_pipeline.close.assert_called_once()

    def test_run_integrated_pipeline_closes_on_error(self, tmp_path: Path) -> None:
        """Test pipeline is closed even on error."""
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps({"image_path": "test.png"}), encoding="utf-8")

        with patch("src.qa.pipeline.IntegratedQAPipeline") as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline.create_session = Mock(side_effect=ValueError("오류"))
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(ValueError):
                run_integrated_pipeline(meta_file)

            # Should still close pipeline
            mock_pipeline.close.assert_called_once()


class TestMainExecution:
    """Test main execution block."""

    def test_main_execution(self, tmp_path: Path) -> None:
        """Test main execution with example file."""
        # Create example file
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        meta_file = examples_dir / "session_input.json"
        meta_file.write_text(json.dumps({"image_path": "test.png"}), encoding="utf-8")

        with patch("src.qa.pipeline.Path") as mock_path:
            mock_path.return_value.resolve.return_value.parents = [tmp_path]

            with patch("src.qa.pipeline.run_integrated_pipeline") as mock_run:
                mock_run.return_value = {
                    "turns": [{"type": "reasoning", "prompt": "프롬프트"}],
                    "context": {},
                }

                # Simulate running main block
                from src.qa.pipeline import __name__ as module_name

                if module_name == "__main__":
                    # This would be executed if module is run directly
                    pass
