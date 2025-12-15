"""Tests for OCR router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from src.web.api import app

    return TestClient(app)


@pytest.fixture
def mock_config() -> MagicMock:
    """Create mock AppConfig."""
    config = MagicMock()
    config.ocr_text_path = Path("/tmp/ocr.txt")
    return config


class TestOcrHelperFunctions:
    """Tests for OCR helper functions."""

    def test_set_dependencies(self) -> None:
        """Test set_dependencies sets module-level vars."""
        from src.web.routers import ocr

        mock_config = MagicMock()
        mock_provider = MagicMock()

        ocr.set_dependencies(mock_config, mock_provider)

        assert ocr._config is mock_config
        assert ocr._llm_provider is mock_provider

    def test_get_config_not_initialized(self) -> None:
        """Test _get_config raises when not initialized."""
        from src.web.routers import ocr

        original = ocr._config
        ocr._config = None

        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                ocr._get_config()
        finally:
            ocr._config = original

    def test_get_request_id(self) -> None:
        """Test _get_request_id extracts ID from request state."""
        from src.web.routers.ocr import _get_request_id

        mock_request = MagicMock()
        mock_request.state.request_id = "test-123"

        result = _get_request_id(mock_request)

        assert result == "test-123"

    def test_get_request_id_missing(self) -> None:
        """Test _get_request_id returns empty string when missing."""
        from src.web.routers.ocr import _get_request_id

        mock_request = MagicMock()
        del mock_request.state.request_id

        result = _get_request_id(mock_request)

        assert result == ""


class TestGetOcrEndpoint:
    """Tests for GET /api/ocr endpoint."""

    def test_get_ocr_success(self, client: TestClient, mock_config: MagicMock) -> None:
        """Test successful OCR text retrieval."""
        from src.web.routers import ocr

        ocr.set_dependencies(mock_config)

        with patch(
            "src.web.routers.ocr._load_ocr_text",
            new_callable=AsyncMock,
            return_value="Extracted text",
        ):
            response = client.get("/api/ocr")

            assert response.status_code == 200
            assert response.json()["ocr"] == "Extracted text"

    def test_get_ocr_exception(
        self, client: TestClient, mock_config: MagicMock
    ) -> None:
        """Test get OCR handles exceptions."""
        from src.web.routers import ocr

        ocr.set_dependencies(mock_config)

        with patch(
            "src.web.routers.ocr._load_ocr_text",
            new_callable=AsyncMock,
            side_effect=Exception("Read error"),
        ):
            response = client.get("/api/ocr")

            assert response.status_code == 500


class TestSaveOcrEndpoint:
    """Tests for POST /api/ocr endpoint."""

    def test_save_ocr_success(self, client: TestClient, mock_config: MagicMock) -> None:
        """Test successful OCR text save."""
        from src.web.routers import ocr

        ocr.set_dependencies(mock_config)

        with patch(
            "src.web.routers.ocr._save_ocr_text",
            new_callable=AsyncMock,
        ):
            response = client.post("/api/ocr", json={"text": "New OCR text"})

            assert response.status_code == 200
            assert response.json()["status"] == "success"

    def test_save_ocr_exception(
        self, client: TestClient, mock_config: MagicMock
    ) -> None:
        """Test save OCR handles exceptions."""
        from src.web.routers import ocr

        ocr.set_dependencies(mock_config)

        with patch(
            "src.web.routers.ocr._save_ocr_text",
            new_callable=AsyncMock,
            side_effect=Exception("Write error"),
        ):
            response = client.post("/api/ocr", json={"text": "Test"})

            assert response.status_code == 500


class TestOcrImageEndpoint:
    """Tests for POST /api/ocr/image endpoint."""

    def test_ocr_image_no_provider(
        self, client: TestClient, mock_config: MagicMock
    ) -> None:
        """Test OCR image fails without LLM provider."""
        from src.web.routers import ocr

        ocr.set_dependencies(mock_config, llm_provider=None)

        # Create fake image content
        response = client.post(
            "/api/ocr/image",
            files={"file": ("test.png", b"fake image data", "image/png")},
        )

        assert response.status_code == 503
        assert "LLM Provider" in response.json()["detail"]

    def test_ocr_image_invalid_content_type(
        self, client: TestClient, mock_config: MagicMock
    ) -> None:
        """Test OCR image rejects unsupported content types."""
        from src.web.routers import ocr

        mock_provider = MagicMock()
        ocr.set_dependencies(mock_config, llm_provider=mock_provider)

        response = client.post(
            "/api/ocr/image",
            files={"file": ("test.pdf", b"pdf data", "application/pdf")},
        )

        assert response.status_code == 400
        assert "지원하지 않는" in response.json()["detail"]

    def test_ocr_image_success(
        self,
        client: TestClient,
        mock_config: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successful image OCR."""
        from src.web.routers import ocr

        mock_provider = MagicMock()
        ocr.set_dependencies(mock_config, llm_provider=mock_provider)

        mock_result = {
            "extracted_text": "OCR result text",
            "text_density": 0.8,
            "topics": ["topic1"],
            "has_table_chart": False,
        }

        # Create proper async context manager
        mock_file_handle = MagicMock()
        mock_file_handle.write = AsyncMock()

        async def mock_aenter(self: MagicMock) -> MagicMock:
            return mock_file_handle

        async def mock_aexit(
            self: MagicMock, exc_type: type, exc: Exception, tb: object
        ) -> None:
            pass

        mock_open_cm = MagicMock()
        mock_open_cm.__aenter__ = mock_aenter
        mock_open_cm.__aexit__ = mock_aexit

        def mock_aiofiles_open(*args: object, **kwargs: object) -> MagicMock:
            return mock_open_cm

        # Patch aiofiles.open where it's USED, not where it's DEFINED
        monkeypatch.setattr("src.web.routers.ocr.aiofiles.open", mock_aiofiles_open)

        mock_multimodal = MagicMock()
        mock_multimodal.analyze_image_deep = AsyncMock(return_value=mock_result)

        with (
            patch(
                "src.web.routers.ocr.MultimodalUnderstanding",
                return_value=mock_multimodal,
            ),
            patch("src.web.routers.ocr._save_ocr_text", new_callable=AsyncMock),
        ):
            response = client.post(
                "/api/ocr/image",
                files={"file": ("test.png", b"PNG image data", "image/png")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["ocr"] == "OCR result text"
            assert data["metadata"]["text_density"] == 0.8

    def test_ocr_image_exception(
        self, client: TestClient, mock_config: MagicMock
    ) -> None:
        """Test OCR image handles processing exceptions."""
        from src.web.routers import ocr

        mock_provider = MagicMock()
        ocr.set_dependencies(mock_config, llm_provider=mock_provider)

        with patch(
            "src.web.routers.ocr.MultimodalUnderstanding"
        ) as mock_multimodal_cls:
            mock_instance = MagicMock()
            mock_instance.analyze_image_deep = AsyncMock(
                side_effect=Exception("OCR processing error")
            )
            mock_multimodal_cls.return_value = mock_instance

            response = client.post(
                "/api/ocr/image",
                files={"file": ("test.jpg", b"JPEG data", "image/jpeg")},
            )

            assert response.status_code == 500

    def test_ocr_image_no_extracted_text(
        self,
        client: TestClient,
        mock_config: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test OCR image handles empty extracted text."""
        from src.web.routers import ocr

        mock_provider = MagicMock()
        ocr.set_dependencies(mock_config, llm_provider=mock_provider)

        mock_result = {
            "extracted_text": "",
            "text_density": 0.0,
        }

        # Create proper async context manager
        mock_file_handle = MagicMock()
        mock_file_handle.write = AsyncMock()

        async def mock_aenter(self: MagicMock) -> MagicMock:
            return mock_file_handle

        async def mock_aexit(
            self: MagicMock, exc_type: type, exc: Exception, tb: object
        ) -> None:
            pass

        mock_open_cm = MagicMock()
        mock_open_cm.__aenter__ = mock_aenter
        mock_open_cm.__aexit__ = mock_aexit

        def mock_aiofiles_open(*args: object, **kwargs: object) -> MagicMock:
            return mock_open_cm

        # Patch aiofiles.open where it's USED, not where it's DEFINED
        monkeypatch.setattr("src.web.routers.ocr.aiofiles.open", mock_aiofiles_open)

        mock_multimodal = MagicMock()
        mock_multimodal.analyze_image_deep = AsyncMock(return_value=mock_result)

        with (
            patch(
                "src.web.routers.ocr.MultimodalUnderstanding",
                return_value=mock_multimodal,
            ),
            patch(
                "src.web.routers.ocr._save_ocr_text", new_callable=AsyncMock
            ) as mock_save,
        ):
            response = client.post(
                "/api/ocr/image",
                files={"file": ("test.gif", b"GIF data", "image/gif")},
            )

            assert response.status_code == 200
            # Should not save empty text
            mock_save.assert_not_called()
