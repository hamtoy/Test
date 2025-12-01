from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PIL")

from PIL import Image

from scripts import ocr_extraction


def test_preprocess_image_upscaling() -> None:
    """Test that low-resolution images are upscaled."""
    # Create a small test image (800x600)
    small_img = Image.new("RGB", (800, 600), color="white")

    # Preprocess should upscale it
    result = ocr_extraction._preprocess_image(small_img)

    # After upscaling, width or height should be >= 1000
    assert result.size[0] >= 1000 or result.size[1] >= 1000


def test_preprocess_image_contrast_enhancement() -> None:
    """Test that contrast enhancement is applied."""
    img = Image.new("RGB", (1200, 1200), color="white")

    # The function should complete without error
    result = ocr_extraction._preprocess_image(img)
    assert result is not None
    assert isinstance(result, Image.Image)


def test_preprocess_image_defaults() -> None:
    """Test that grayscale and binarize are False by default."""
    img = Image.new("RGB", (1200, 1200), color=(128, 64, 192))

    # With default settings, should preserve color
    result = ocr_extraction._preprocess_image(img)

    # Image should still be RGB (not grayscale)
    assert result.mode in ("RGB", "RGBA")


def test_preprocess_image_max_dim() -> None:
    """Test that max_dim is respected."""
    # Create a large image
    large_img = Image.new("RGB", (3000, 2000), color="white")

    # Preprocess with default max_dim (2048, 2048)
    result = ocr_extraction._preprocess_image(large_img)

    # Result should be within max_dim
    assert result.size[0] <= 2048
    assert result.size[1] <= 2048


def test_extract_with_retries_layout_prompt() -> None:
    """Test that layout prompt is selected correctly."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Test OCR result"
    mock_model.generate_content.return_value = mock_response

    # Create a small test image
    test_img = Image.new("RGB", (100, 100), color="white")
    test_path = Path("/tmp/test_image.png")

    with patch("scripts.ocr_extraction.Image.open") as mock_open:
        mock_open.return_value.__enter__.return_value = test_img

        # Test with layout prompt
        text, error = ocr_extraction._extract_with_retries(
            mock_model, test_path, preprocess=False, use_layout_prompt=True
        )

        assert text == "Test OCR result"
        assert error is None

        # Verify the correct prompt was used
        call_args = mock_model.generate_content.call_args
        assert call_args is not None
        prompt_used = call_args[0][0][0]
        assert "금융/경제 뉴스" in prompt_used


def test_extract_with_retries_default_prompt() -> None:
    """Test that default prompt is used when layout prompt is False."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Test OCR result"
    mock_model.generate_content.return_value = mock_response

    # Create a small test image
    test_img = Image.new("RGB", (100, 100), color="white")
    test_path = Path("/tmp/test_image.png")

    with patch("scripts.ocr_extraction.Image.open") as mock_open:
        mock_open.return_value.__enter__.return_value = test_img

        # Test with default prompt
        text, error = ocr_extraction._extract_with_retries(
            mock_model, test_path, preprocess=False, use_layout_prompt=False
        )

        assert text == "Test OCR result"
        assert error is None

        # Verify the correct prompt was used
        call_args = mock_model.generate_content.call_args
        assert call_args is not None
        prompt_used = call_args[0][0][0]
        assert "한국어 문서 OCR 전문가" in prompt_used


def test_ocr_prompt_constants() -> None:
    """Test that OCR prompt constants are defined."""
    # Check that both prompts exist and contain expected content
    assert ocr_extraction.OCR_PROMPT is not None
    assert "한국어" in ocr_extraction.OCR_PROMPT

    assert ocr_extraction.OCR_PROMPT_LAYOUT is not None
    assert "금융/경제 뉴스" in ocr_extraction.OCR_PROMPT_LAYOUT


def test_preprocess_max_dim_constant() -> None:
    """Test that PREPROCESS_MAX_DIM is updated to (2048, 2048)."""
    assert ocr_extraction.PREPROCESS_MAX_DIM == (2048, 2048)
