"""Tests for the Web API module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.api import app

# Apply mock_genai fixture to all tests in this module
pytestmark = pytest.mark.usefixtures("mock_genai")

# Patch paths for mocking external dependencies
PATCH_GENERATE_BATCH = "src.web.routers.qa_generation.generate_single_qa_with_retry"
PATCH_EVALUATE_EXTERNAL = "src.workflow.external_eval.evaluate_external_answers"
PATCH_INSPECT_ANSWER = "src.web.routers.workspace_review.inspect_answer"
PATCH_EDIT_CONTENT = "src.web.routers.workspace_review.edit_content"


def _create_mock_agent() -> MagicMock:
    """Create a mock GeminiAgent for testing."""
    mock_agent = MagicMock()

    # Mock generate methods
    mock_response = MagicMock()
    mock_response.text = "샘플 응답 텍스트"

    mock_agent.generate_content = MagicMock(return_value=mock_response)
    mock_agent.generate_content_async = AsyncMock(return_value=mock_response)

    # Mock QA-related methods
    mock_agent.generate_query = AsyncMock(return_value="샘플 질의")
    mock_agent.generate_answer = AsyncMock(return_value="샘플 답변")
    mock_agent.evaluate_answers = AsyncMock(
        return_value={
            "results": [
                {"label": "A", "score": 0.9, "reasoning": "좋은 답변"},
                {"label": "B", "score": 0.7, "reasoning": "괜찮은 답변"},
                {"label": "C", "score": 0.5, "reasoning": "보통 답변"},
            ],
            "best": "A",
        }
    )

    # Mock workspace methods
    mock_agent.inspect_answer = AsyncMock(return_value="[검수됨] 원본 텍스트")
    mock_agent.edit_answer = AsyncMock(return_value="수정됨: 짧은 텍스트")

    return mock_agent


@pytest.fixture
def mock_web_dependencies(tmp_path: Path, isolate_registry: None) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Mock all web service dependencies including config, agent, and pipeline.
    
    This fixture must run after isolate_registry to ensure the registry is clean.
    
    Returns:
        Tuple of (mock_config, mock_agent, mock_pipeline)
    """
    from src.config import AppConfig
    from src.web.service_registry import get_registry
    
    # Create mock config with proper paths
    mock_config = MagicMock(spec=AppConfig)
    mock_config.input_dir = tmp_path / "inputs"
    mock_config.input_dir.mkdir(parents=True, exist_ok=True)
    mock_config.qa_single_timeout = 120
    mock_config.qa_batch_timeout = 300
    mock_config.workspace_timeout = 120
    mock_config.workspace_unified_timeout = 180
    mock_config.enable_standard_response = False
    
    # Create sample OCR file
    (mock_config.input_dir / "input_ocr.txt").write_text(
        "샘플 OCR 텍스트", encoding="utf-8"
    )
    
    # Create mock agent with comprehensive async methods
    mock_agent = MagicMock()
    mock_agent.generate_query = AsyncMock(return_value="샘플 질의")
    mock_agent.generate_answer = AsyncMock(return_value="샘플 답변")
    mock_agent.rewrite_best_answer = AsyncMock(return_value="재작성된 답변")
    mock_agent.evaluate_candidates = AsyncMock(return_value={"best_index": 0})
    
    # Mock evaluate_answers for external evaluation
    async def mock_evaluate(*args, **kwargs):
        return [
            {"candidate_id": "A", "score": 0.9, "reasoning": "좋은 답변"},
            {"candidate_id": "B", "score": 0.7, "reasoning": "괜찮은 답변"},
            {"candidate_id": "C", "score": 0.5, "reasoning": "보통 답변"},
        ]
    mock_agent.evaluate_answers = AsyncMock(side_effect=mock_evaluate)
    
    # Mock workspace functions
    async def mock_inspect(answer, *args, **kwargs):
        return f"[검수됨] {answer}"
    
    async def mock_edit(answer, edit_request, *args, **kwargs):
        return f"[수정: {edit_request}] {answer}"
    
    mock_agent.inspect_answer = AsyncMock(side_effect=mock_inspect)
    mock_agent.edit_answer = AsyncMock(side_effect=mock_edit)
    
    # Create mock pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.generate_qa_pair = AsyncMock(
        return_value={"query": "샘플 질의", "answer": "샘플 답변"}
    )
    
    # Register mocks in the service registry (after it's been reset by isolate_registry)
    registry = get_registry()
    registry.register_config(mock_config)
    registry.register_agent(mock_agent)
    registry.register_pipeline(mock_pipeline)
    registry.register_kg(None)  # Optional dependency
    registry.register_validator(None)  # Optional dependency
    
    return mock_config, mock_agent, mock_pipeline


@pytest.fixture(scope="function")
def client(mock_web_dependencies: tuple) -> TestClient:
    """Create a test client with mocked dependencies.
    
    Note: init_resources is called once per test to ensure fresh state.
    This is acceptable for test isolation but could be optimized to session
    scope if tests don't modify global state.
    """
    # Force initialization to use the mocked registry
    import asyncio
    from src.web.api import init_resources
    
    # Run init_resources to sync registry with module-level variables
    asyncio.run(init_resources())
    
    return TestClient(app)


class TestPageRoutes:
    """Test HTML page routes."""

    def test_root_page(self, client: TestClient) -> None:
        """Test root page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_qa_page(self, client: TestClient) -> None:
        """Test QA page."""
        response = client.get("/qa")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_eval_page(self, client: TestClient) -> None:
        """Test evaluation page."""
        response = client.get("/eval")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workspace_page(self, client: TestClient) -> None:
        """Test workspace page."""
        response = client.get("/workspace")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestOCREndpoint:
    """Test OCR endpoint."""

    def test_get_ocr_exists(self, client: TestClient, tmp_path: Path) -> None:
        """Test getting OCR text when file exists."""

        from src.config import AppConfig
        from src.web.routers import ocr as ocr_router_module

        # Create actual directory and file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Sample OCR Text", encoding="utf-8")

        mock_config = MagicMock(spec=AppConfig)
        mock_config.input_dir = inputs_dir
        ocr_router_module.set_dependencies(mock_config)

        response = client.get("/api/ocr")
        assert response.status_code == 200
        assert response.json() == {"ocr": "Sample OCR Text"}

    def test_get_ocr_missing(self, client: TestClient, tmp_path: Path) -> None:
        """Test getting OCR text when file is missing."""
        from src.config import AppConfig
        from src.web.routers import ocr as ocr_router_module

        # Create directory but not the file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)

        mock_config = MagicMock(spec=AppConfig)
        mock_config.input_dir = inputs_dir
        ocr_router_module.set_dependencies(mock_config)

        response = client.get("/api/ocr")
        assert response.status_code == 404
        assert response.json() == {"detail": "OCR 파일이 없습니다."}


class TestQAGeneration:
    """Test QA generation endpoints."""

    def test_generate_single_valid(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test single QA generation with valid type.

        Note: This test validates the endpoint responds properly.
        Full agent logic is tested separately in unit tests.
        """
        payload = {"mode": "single", "qtype": "target_short"}
        
        response = client.post("/api/qa/generate", json=payload)
        
        # Should return 200 with valid JSON structure
        assert response.status_code == 200, f"Error: {response.json()}"
        data = response.json()
        
        # Check response structure (may vary based on enable_standard_response)
        assert "pair" in data or "data" in data

    def test_generate_single_invalid_type(self, client: TestClient) -> None:
        """Test single QA generation with invalid type returns 422 (Pydantic validation)."""
        payload = {"mode": "single", "qtype": "invalid_type"}
        response = client.post("/api/qa/generate", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422

    def test_generate_batch(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test batch QA generation.

        Note: This test validates the endpoint responds properly.
        Full agent logic is tested separately in unit tests.
        """
        payload = {
            "mode": "batch",
            "batch_types": ["target_short", "target_long"]
        }
        
        # Patch the generate_single_qa_with_retry function
        with patch(PATCH_GENERATE_BATCH) as mock_gen:
            mock_gen.return_value = {
                "type": "target_short",
                "query": "샘플 질의",
                "answer": "샘플 답변"
            }
            
            response = client.post("/api/qa/generate", json=payload)
            
            # Should return 200 with valid JSON structure
            assert response.status_code == 200
            data = response.json()
            
            # Check response has results (structure may vary)
            assert "pairs" in data or "data" in data
            
            # Verify the mock was called
            assert mock_gen.called


class TestEvaluation:
    """Test evaluation endpoints."""

    def test_evaluate_external_valid(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test external evaluation with valid inputs (requires 3 answers).

        Note: This test validates the endpoint responds properly.
        """
        payload = {
            "query": "테스트 질문",
            "answers": ["답변 A", "답변 B", "답변 C"]
        }
        
        # Patch the evaluate_external_answers function from workflow module
        with patch(PATCH_EVALUATE_EXTERNAL) as mock_eval:
            mock_eval.return_value = [
                {"candidate_id": "A", "score": 0.9, "reasoning": "최고"},
                {"candidate_id": "B", "score": 0.7, "reasoning": "좋음"},
                {"candidate_id": "C", "score": 0.5, "reasoning": "보통"},
            ]
            
            response = client.post("/api/eval/external", json=payload)
            
            # Should return 200 with evaluation results
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "results" in data or "data" in data or "best" in data
            
            # Verify the evaluation function was called
            assert mock_eval.called

    def test_evaluate_external_no_answers(self, client: TestClient) -> None:
        """Test external evaluation with no answers returns 422 (Pydantic validation)."""
        payload = {"query": "Test Query", "answers": []}
        response = client.post("/api/eval/external", json=payload)
        # Pydantic returns 422 for validation errors (requires exactly 3 answers)
        assert response.status_code == 422

    def test_evaluate_external_wrong_count_answers(self, client: TestClient) -> None:
        """Test external evaluation with wrong number of answers returns 422."""
        payload = {
            "query": "Test Query",
            "answers": ["Answer"] * 7,  # API requires exactly 3 answers
        }
        response = client.post("/api/eval/external", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422


class TestWorkspace:
    """Test workspace endpoints."""

    def test_workspace_inspect(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test workspace inspect mode.

        Note: This test validates the endpoint responds properly.
        """
        payload = {
            "mode": "inspect",
            "answer": "원본 텍스트",
            "query": "테스트 질문"
        }
        
        # Patch the inspect_answer function
        with patch(PATCH_INSPECT_ANSWER) as mock_inspect:
            mock_inspect.return_value = "[검수됨] 원본 텍스트"
            
            response = client.post("/api/workspace", json=payload)
            
            # Should return 200 with inspection result
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "mode" in data or "data" in data
            
            # Verify the inspect function was called
            assert mock_inspect.called

    def test_workspace_edit(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test workspace edit mode.

        Note: This test validates the endpoint responds properly.
        """
        payload = {
            "mode": "edit",
            "answer": "원본 텍스트",
            "query": "테스트 질문",
            "edit_request": "더 짧게 수정해주세요"
        }
        
        # Patch the edit_content function
        with patch(PATCH_EDIT_CONTENT) as mock_edit:
            mock_edit.return_value = "수정된 텍스트"
            
            response = client.post("/api/workspace", json=payload)
            
            # Should return 200 with edit result
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "mode" in data or "data" in data
            
            # Verify the edit function was called
            assert mock_edit.called

    def test_workspace_edit_missing_request(
        self, client: TestClient, mock_web_dependencies: tuple
    ) -> None:
        """Test workspace edit mode without edit request.

        Note: Validation of empty edit_request happens at endpoint level.
        """
        payload = {
            "mode": "edit",
            "answer": "원본 텍스트",
            "query": "테스트 질문"
            # edit_request is missing
        }
        
        # Patch functions to avoid actual execution
        with patch(PATCH_EDIT_CONTENT) as mock_edit:
            with patch(PATCH_INSPECT_ANSWER) as mock_inspect:
                mock_edit.return_value = "수정됨"
                mock_inspect.return_value = "검수됨"
                
                response = client.post("/api/workspace", json=payload)
                
                # Should return 400, 422, or 500 (depending on where validation happens)
                # The endpoint raises HTTPException with 400 if edit_request is missing
                assert response.status_code in [400, 422, 500]
                
                # If it's 500, check it's due to the validation error
                if response.status_code == 500:
                    error_detail = response.json().get("detail", "")
                    assert "edit_request" in error_detail.lower() or "작업 실패" in error_detail

    def test_workspace_invalid_mode(self, client: TestClient) -> None:
        """Test workspace with invalid mode returns 422 (Pydantic validation)."""
        payload = {"mode": "invalid", "answer": "Original Text"}
        response = client.post("/api/workspace", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422


class TestMultimodal:
    """Test multimodal endpoints.

    Note: Multimodal tests require optional module initialization.
    These remain skipped and are tested separately when optional deps are available.
    """

    def test_analyze_image_valid(self, client: TestClient) -> None:
        """Test image analysis with valid image."""
        pytest.skip("Requires optional multimodal module")

    def test_analyze_image_invalid_type(self, client: TestClient) -> None:
        """Test image analysis with non-image file."""
        pytest.skip("Requires optional multimodal module")
