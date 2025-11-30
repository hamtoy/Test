"""Tests for src/core/schemas.py - data validation schemas."""

import pytest
from pydantic import ValidationError

from src.core.schemas import (
    CandidateAnswer,
    EvaluationRequest,
    OCRInput,
    QAGenerationRequest,
)


class TestOCRInput:
    """Test OCRInput schema validation."""

    def test_valid_ocr_input(self) -> None:
        """Test valid OCR input creation."""
        text = "This is a valid OCR text with more than 10 characters."
        ocr = OCRInput(text=text)
        assert ocr.text == text
        assert ocr.language == "ko"  # Default

    def test_valid_ocr_input_with_english(self) -> None:
        """Test OCR input with English language."""
        text = "This is a valid English OCR text."
        ocr = OCRInput(text=text, language="en")
        assert ocr.language == "en"

    def test_ocr_input_text_too_short(self) -> None:
        """Test OCR input validation fails for short text."""
        with pytest.raises(ValidationError) as exc_info:
            OCRInput(text="Short")
        assert "String should have at least 10 characters" in str(exc_info.value)

    def test_ocr_input_empty_text(self) -> None:
        """Test OCR input validation fails for empty text."""
        with pytest.raises(ValidationError):
            OCRInput(text="")

    def test_ocr_input_whitespace_only(self) -> None:
        """Test OCR input validation fails for whitespace-only text."""
        with pytest.raises(ValidationError) as exc_info:
            OCRInput(text="            ")  # Just whitespace, enough chars
        assert "OCR 텍스트가 비어있습니다" in str(exc_info.value)

    def test_ocr_input_special_chars_only(self) -> None:
        """Test OCR input validation fails when only special chars."""
        with pytest.raises(ValidationError) as exc_info:
            OCRInput(text="!@#$%^&*()_+-={}[]|;':\",./<>?")
        assert "유효한 텍스트가 부족합니다" in str(exc_info.value)

    def test_ocr_input_valid_korean(self) -> None:
        """Test OCR input with valid Korean text."""
        text = "이것은 유효한 한국어 OCR 텍스트입니다."
        ocr = OCRInput(text=text, language="ko")
        assert ocr.text == text
        assert ocr.language == "ko"


class TestCandidateAnswer:
    """Test CandidateAnswer schema validation."""

    def test_valid_candidate_answer(self) -> None:
        """Test valid candidate answer creation."""
        content = "This is a valid candidate answer content."
        answer = CandidateAnswer(id="A", content=content)
        assert answer.id == "A"
        assert answer.content == content

    def test_valid_candidate_id_b(self) -> None:
        """Test candidate answer with ID B."""
        content = "Another valid candidate answer."
        answer = CandidateAnswer(id="B", content=content)
        assert answer.id == "B"

    def test_valid_candidate_id_c(self) -> None:
        """Test candidate answer with ID C."""
        content = "Yet another valid candidate answer."
        answer = CandidateAnswer(id="C", content=content)
        assert answer.id == "C"

    def test_invalid_candidate_id(self) -> None:
        """Test invalid candidate ID fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            CandidateAnswer(id="D", content="Valid content here for test.")
        assert "Input should be 'A', 'B' or 'C'" in str(exc_info.value)

    def test_content_too_short(self) -> None:
        """Test content too short fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            CandidateAnswer(id="A", content="Short")
        assert "String should have at least 10 characters" in str(exc_info.value)


class TestEvaluationRequest:
    """Test EvaluationRequest schema validation."""

    def test_valid_evaluation_request(self) -> None:
        """Test valid evaluation request creation."""
        candidates = [
            CandidateAnswer(id="A", content="First candidate answer here."),
            CandidateAnswer(id="B", content="Second candidate answer here."),
        ]
        request = EvaluationRequest(
            query="What is the answer to this question?", candidates=candidates
        )
        assert request.query == "What is the answer to this question?"
        assert len(request.candidates) == 2

    def test_evaluation_request_with_three_candidates(self) -> None:
        """Test evaluation request with three candidates."""
        candidates = [
            CandidateAnswer(id="A", content="First candidate answer here."),
            CandidateAnswer(id="B", content="Second candidate answer here."),
            CandidateAnswer(id="C", content="Third candidate answer here."),
        ]
        request = EvaluationRequest(query="Valid query text", candidates=candidates)
        assert len(request.candidates) == 3

    def test_query_too_short(self) -> None:
        """Test query too short fails validation."""
        candidates = [
            CandidateAnswer(id="A", content="First candidate answer here."),
            CandidateAnswer(id="B", content="Second candidate answer here."),
        ]
        with pytest.raises(ValidationError) as exc_info:
            EvaluationRequest(query="Hi", candidates=candidates)
        assert "String should have at least 5 characters" in str(exc_info.value)

    def test_too_few_candidates(self) -> None:
        """Test fewer than 2 candidates fails validation."""
        candidates = [
            CandidateAnswer(id="A", content="First candidate answer here."),
        ]
        with pytest.raises(ValidationError) as exc_info:
            EvaluationRequest(query="Valid query text", candidates=candidates)
        assert "List should have at least 2 items" in str(exc_info.value)

    def test_duplicate_candidate_ids(self) -> None:
        """Test duplicate candidate IDs fail validation."""
        candidates = [
            CandidateAnswer(id="A", content="First candidate answer here."),
            CandidateAnswer(id="A", content="Second candidate answer here."),
        ]
        with pytest.raises(ValidationError) as exc_info:
            EvaluationRequest(query="Valid query text", candidates=candidates)
        assert "후보 ID가 중복됩니다" in str(exc_info.value)


class TestQAGenerationRequest:
    """Test QAGenerationRequest schema validation."""

    def test_batch_mode_without_qtype(self) -> None:
        """Test batch mode without qtype is valid."""
        request = QAGenerationRequest(mode="batch")
        assert request.mode == "batch"
        assert request.qtype is None

    def test_batch_mode_with_qtype(self) -> None:
        """Test batch mode with qtype is valid."""
        request = QAGenerationRequest(mode="batch", qtype="reasoning")
        assert request.mode == "batch"
        assert request.qtype == "reasoning"

    def test_single_mode_with_qtype(self) -> None:
        """Test single mode with qtype is valid."""
        request = QAGenerationRequest(mode="single", qtype="global_explanation")
        assert request.mode == "single"
        assert request.qtype == "global_explanation"

    def test_single_mode_without_qtype_fails(self) -> None:
        """Test single mode without qtype fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            QAGenerationRequest(mode="single")
        assert "single 모드에서는 qtype 필수" in str(exc_info.value)

    def test_all_qtype_values(self) -> None:
        """Test all valid qtype values."""
        qtypes = ["global_explanation", "reasoning", "target_short", "target_long"]
        for qtype in qtypes:
            request = QAGenerationRequest(mode="single", qtype=qtype)
            assert request.qtype == qtype

    def test_invalid_mode(self) -> None:
        """Test invalid mode fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            QAGenerationRequest(mode="invalid")
        assert "Input should be 'batch' or 'single'" in str(exc_info.value)


class TestAllExports:
    """Test __all__ exports are available."""

    def test_all_exports(self) -> None:
        """Test all exports are available."""
        from src.core import schemas

        assert "OCRInput" in schemas.__all__
        assert "CandidateAnswer" in schemas.__all__
        assert "EvaluationRequest" in schemas.__all__
        assert "QAGenerationRequest" in schemas.__all__
