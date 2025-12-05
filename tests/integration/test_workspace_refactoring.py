"""Integration test for refactored workspace router.

This test verifies that the refactored api_unified_workspace endpoint
works correctly with WorkspaceExecutor.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.web.routers.workspace import api_unified_workspace
from src.web.models import UnifiedWorkspaceRequest
from src.workflow.workspace_executor import WorkflowResult


@pytest.mark.asyncio
async def test_api_unified_workspace_uses_executor() -> None:
    """Test that api_unified_workspace uses WorkspaceExecutor."""
    # Create a mock request
    request = UnifiedWorkspaceRequest(
        query="테스트 질문",
        answer="테스트 답변",
        ocr_text="테스트 OCR 텍스트",
        query_type="global_explanation",
        edit_request="",
        global_explanation_ref="",
        use_lats=False,
    )

    # Mock the executor and its result
    mock_result = WorkflowResult(
        workflow="full_generation",
        query="테스트 질문",
        answer="테스트 답변",
        changes=["OCR에서 전체 생성", "질의 생성 완료", "답변 생성 완료"],
        query_type="global_explanation",
    )

    # Patch all the required dependencies
    with (
        patch("src.web.routers.workspace._get_agent") as mock_get_agent,
        patch("src.web.routers.workspace._get_kg") as mock_get_kg,
        patch("src.web.routers.workspace._get_pipeline") as mock_get_pipeline,
        patch("src.web.routers.workspace._get_config") as mock_get_config,
        patch("src.web.routers.workspace.load_ocr_text") as mock_load_ocr,
        patch("src.workflow.workspace_executor.WorkspaceExecutor") as MockExecutor,
    ):
        # Setup mocks
        mock_agent = Mock()
        mock_get_agent.return_value = mock_agent
        mock_get_kg.return_value = None
        mock_get_pipeline.return_value = None

        mock_config = Mock()
        mock_config.workspace_unified_timeout = 300
        mock_config.enable_standard_response = False
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "테스트 OCR 텍스트"

        # Setup executor mock
        mock_executor_instance = Mock()
        mock_executor_instance.execute = AsyncMock(return_value=mock_result)
        MockExecutor.return_value = mock_executor_instance

        # Call the endpoint
        response = await api_unified_workspace(request)

        # Verify executor was created and called
        MockExecutor.assert_called_once()
        mock_executor_instance.execute.assert_called_once()

        # Verify response structure
        assert "data" in response or "workflow" in response
        print("✓ api_unified_workspace successfully uses WorkspaceExecutor")


@pytest.mark.asyncio
async def test_api_unified_workspace_workflow_detection() -> None:
    """Test that workflow detection works correctly."""
    # Test different scenarios
    test_cases = [
        {
            "query": "",
            "answer": "",
            "edit_request": "",
            "expected_workflow": "full_generation",
        },
        {
            "query": "질문만 있음",
            "answer": "",
            "edit_request": "",
            "expected_workflow": "answer_generation",
        },
        {
            "query": "",
            "answer": "답변만 있음",
            "edit_request": "",
            "expected_workflow": "query_generation",
        },
    ]

    for case in test_cases:
        request = UnifiedWorkspaceRequest(
            query=case["query"],
            answer=case["answer"],
            ocr_text="테스트 OCR",
            query_type="global_explanation",
            edit_request=case["edit_request"],
            global_explanation_ref="",
            use_lats=False,
        )

        mock_result = WorkflowResult(
            workflow=case["expected_workflow"],
            query=case["query"] or "생성된 질문",
            answer=case["answer"] or "생성된 답변",
            changes=["테스트 완료"],
            query_type="global_explanation",
        )

        with (
            patch("src.web.routers.workspace._get_agent") as mock_get_agent,
            patch("src.web.routers.workspace._get_kg"),
            patch("src.web.routers.workspace._get_pipeline"),
            patch("src.web.routers.workspace._get_config") as mock_get_config,
            patch("src.web.routers.workspace.load_ocr_text") as mock_load_ocr,
            patch("src.workflow.workspace_executor.WorkspaceExecutor") as MockExecutor,
        ):
            mock_agent = Mock()
            mock_get_agent.return_value = mock_agent

            mock_config = Mock()
            mock_config.workspace_unified_timeout = 300
            mock_config.enable_standard_response = False
            mock_get_config.return_value = mock_config

            mock_load_ocr.return_value = "테스트 OCR"

            mock_executor_instance = Mock()
            mock_executor_instance.execute = AsyncMock(return_value=mock_result)
            MockExecutor.return_value = mock_executor_instance

            await api_unified_workspace(request)

            # Verify the workflow was detected correctly
            call_args = mock_executor_instance.execute.call_args
            workflow_type = call_args[0][0]
            assert workflow_type.value == case["expected_workflow"], (
                f"Expected {case['expected_workflow']}, got {workflow_type.value}"
            )

    print("✓ Workflow detection works correctly")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_api_unified_workspace_uses_executor())
    asyncio.run(test_api_unified_workspace_workflow_detection())
    print("\n✓ All integration tests passed!")
