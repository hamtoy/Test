"""Tests for the web API models."""

import pytest
from pydantic import ValidationError

# Import directly to avoid api.py's heavy dependencies
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("web_models", "src/web/models.py")
if spec is None or spec.loader is None:
    raise ImportError("Could not load spec or loader for src/web/models.py")
web_models = importlib.util.module_from_spec(spec)
sys.modules["web_models"] = web_models
spec.loader.exec_module(web_models)

EvalExternalRequest = web_models.EvalExternalRequest
EvalExternalResponse = web_models.EvalExternalResponse
EvalResult = web_models.EvalResult
GenerateQARequest = web_models.GenerateQARequest
GenerateQAResponse = web_models.GenerateQAResponse
MultimodalResponse = web_models.MultimodalResponse
QAPair = web_models.QAPair
WorkspaceRequest = web_models.WorkspaceRequest
WorkspaceResponse = web_models.WorkspaceResponse


class TestGenerateQARequest:
    """Tests for GenerateQARequest model."""

    def test_batch_mode_valid(self):
        """Test batch mode is valid without qtype."""
        request = GenerateQARequest(mode="batch")
        assert request.mode == "batch"
        assert request.qtype is None

    def test_single_mode_valid(self):
        """Test single mode is valid with qtype."""
        request = GenerateQARequest(mode="single", qtype="global_explanation")
        assert request.mode == "single"
        assert request.qtype == "global_explanation"

    def test_single_mode_all_qtypes(self):
        """Test all valid qtype values."""
        qtypes = ["global_explanation", "reasoning", "target_short", "target_long"]
        for qtype in qtypes:
            request = GenerateQARequest(mode="single", qtype=qtype)
            assert request.qtype == qtype

    def test_invalid_mode(self):
        """Test invalid mode raises validation error."""
        with pytest.raises(ValidationError):
            GenerateQARequest(mode="invalid")

    def test_invalid_qtype(self):
        """Test invalid qtype raises validation error."""
        with pytest.raises(ValidationError):
            GenerateQARequest(mode="single", qtype="invalid_type")


class TestQAPair:
    """Tests for QAPair model."""

    def test_valid_qa_pair(self):
        """Test valid QA pair creation."""
        pair = QAPair(type="reasoning", query="질문입니다", answer="답변입니다")
        assert pair.type == "reasoning"
        assert pair.query == "질문입니다"
        assert pair.answer == "답변입니다"


class TestGenerateQAResponse:
    """Tests for GenerateQAResponse model."""

    def test_batch_response(self):
        """Test batch mode response."""
        pairs = [
            QAPair(type="reasoning", query="Q1", answer="A1"),
            QAPair(type="explanation", query="Q2", answer="A2"),
        ]
        response = GenerateQAResponse(mode="batch", pairs=pairs)
        assert response.mode == "batch"
        assert len(response.pairs) == 2

    def test_single_response(self):
        """Test single mode response."""
        pair = QAPair(type="reasoning", query="Q", answer="A")
        response = GenerateQAResponse(mode="single", pair=pair)
        assert response.mode == "single"
        assert response.pair.query == "Q"


class TestEvalExternalRequest:
    """Tests for EvalExternalRequest model."""

    def test_valid_request(self):
        """Test valid external evaluation request."""
        request = EvalExternalRequest(
            query="테스트 질의",
            answers=["답변1", "답변2", "답변3"],
        )
        assert request.query == "테스트 질의"
        assert len(request.answers) == 3

    def test_too_few_answers(self):
        """Test that fewer than 3 answers raises error."""
        with pytest.raises(ValidationError):
            EvalExternalRequest(
                query="질의",
                answers=["답변1", "답변2"],  # Only 2 answers
            )

    def test_too_many_answers(self):
        """Test that more than 3 answers raises error."""
        with pytest.raises(ValidationError):
            EvalExternalRequest(
                query="질의",
                answers=["답변1", "답변2", "답변3", "답변4"],  # 4 answers
            )


class TestEvalResult:
    """Tests for EvalResult model."""

    def test_valid_result(self):
        """Test valid evaluation result."""
        result = EvalResult(answer_id="A", score=85, feedback="좋은 답변입니다")
        assert result.answer_id == "A"
        assert result.score == 85
        assert result.feedback == "좋은 답변입니다"


class TestEvalExternalResponse:
    """Tests for EvalExternalResponse model."""

    def test_valid_response(self):
        """Test valid external evaluation response."""
        results = [
            EvalResult(answer_id="A", score=80, feedback="Good"),
            EvalResult(answer_id="B", score=90, feedback="Best"),
            EvalResult(answer_id="C", score=70, feedback="OK"),
        ]
        response = EvalExternalResponse(results=results, best="B")
        assert len(response.results) == 3
        assert response.best == "B"


class TestWorkspaceRequest:
    """Tests for WorkspaceRequest model."""

    def test_inspect_mode(self):
        """Test inspect mode request."""
        request = WorkspaceRequest(mode="inspect", answer="검수할 답변")
        assert request.mode == "inspect"
        assert request.answer == "검수할 답변"

    def test_edit_mode(self):
        """Test edit mode request."""
        request = WorkspaceRequest(
            mode="edit",
            answer="수정할 답변",
            edit_request="더 간결하게",
        )
        assert request.mode == "edit"
        assert request.edit_request == "더 간결하게"

    def test_with_query(self):
        """Test request with optional query."""
        request = WorkspaceRequest(
            mode="inspect",
            query="관련 질의",
            answer="답변",
        )
        assert request.query == "관련 질의"

    def test_invalid_mode(self):
        """Test invalid mode raises error."""
        with pytest.raises(ValidationError):
            WorkspaceRequest(mode="invalid", answer="답변")

    def test_inspector_comment_with_value(self):
        """Test inspector_comment field with value."""
        request = WorkspaceRequest(
            mode="inspect",
            answer="답변",
            inspector_comment="검수자 코멘트입니다",
        )
        assert request.inspector_comment == "검수자 코멘트입니다"

    def test_inspector_comment_default_empty(self):
        """Test inspector_comment defaults to empty string."""
        request = WorkspaceRequest(mode="inspect", answer="답변")
        assert request.inspector_comment == ""

    def test_inspector_comment_in_edit_mode(self):
        """Test inspector_comment works in edit mode too."""
        request = WorkspaceRequest(
            mode="edit",
            answer="수정할 답변",
            edit_request="더 간결하게",
            inspector_comment="수정 이유 설명",
        )
        assert request.inspector_comment == "수정 이유 설명"


class TestWorkspaceResponse:
    """Tests for WorkspaceResponse model."""

    def test_inspect_response(self):
        """Test inspect mode response."""
        response = WorkspaceResponse(
            mode="inspect",
            result={"original": "원본", "fixed": "수정됨"},
        )
        assert response.mode == "inspect"
        assert response.result["fixed"] == "수정됨"

    def test_edit_response(self):
        """Test edit mode response."""
        response = WorkspaceResponse(
            mode="edit",
            result={"original": "원본", "edited": "편집됨", "request": "요청"},
        )
        assert response.mode == "edit"
        assert response.result["edited"] == "편집됨"


class TestMultimodalResponse:
    """Tests for MultimodalResponse model."""

    def test_valid_response(self):
        """Test valid multimodal response."""
        response = MultimodalResponse(
            filename="test.png",
            metadata={"text_density": 0.5, "has_table_chart": True},
        )
        assert response.filename == "test.png"
        assert response.metadata["text_density"] == 0.5
