"""WorkspaceExecutor 테스트."""
import pytest
from unittest.mock import AsyncMock, Mock

from src.config import AppConfig
from src.workflow.workspace_executor import (
    WorkflowContext,
    WorkflowResult,
    WorkflowType,
    WorkspaceExecutor,
)


@pytest.fixture
def mock_agent():
    """Mock GeminiAgent."""
    agent = Mock()
    agent.generate_query = AsyncMock(return_value=["테스트 질문입니다?"])
    agent.rewrite_best_answer = AsyncMock(return_value="테스트 답변입니다.")
    return agent


@pytest.fixture
def mock_config():
    """Mock AppConfig."""
    return AppConfig()


@pytest.fixture
def workspace_executor(mock_agent, mock_config):
    """WorkspaceExecutor 인스턴스."""
    return WorkspaceExecutor(
        agent=mock_agent,
        kg=None,
        pipeline=None,
        config=mock_config,
    )


@pytest.fixture
def sample_context():
    """샘플 WorkflowContext."""
    return WorkflowContext(
        query="테스트 질문",
        answer="테스트 답변",
        ocr_text="OCR 텍스트 샘플입니다.",
        query_type="global_explanation",
        edit_request="",
        global_explanation_ref="",
        use_lats=False,
    )


@pytest.mark.asyncio
async def test_full_generation_workflow(workspace_executor, sample_context):
    """전체 생성 워크플로우 테스트."""
    result = await workspace_executor.execute(
        WorkflowType.FULL_GENERATION, sample_context
    )

    assert isinstance(result, WorkflowResult)
    assert result.workflow == "full_generation"
    assert result.query  # 질문이 생성되어야 함
    assert result.answer  # 답변이 생성되어야 함
    assert len(result.changes) > 0


@pytest.mark.asyncio
async def test_query_generation_workflow(workspace_executor, sample_context):
    """질의 생성 워크플로우 테스트."""
    result = await workspace_executor.execute(
        WorkflowType.QUERY_GENERATION, sample_context
    )

    assert result.workflow == "query_generation"
    assert result.query  # 새 질문이 생성되어야 함
    assert result.answer == sample_context.answer  # 기존 답변 유지
    assert "질의 생성" in " ".join(result.changes)


@pytest.mark.asyncio
async def test_answer_generation_workflow(workspace_executor, sample_context):
    """답변 생성 워크플로우 테스트."""
    result = await workspace_executor.execute(
        WorkflowType.ANSWER_GENERATION, sample_context
    )

    assert result.workflow == "answer_generation"
    assert result.query == sample_context.query  # 기존 질문 유지
    assert result.answer  # 새 답변이 생성되어야 함
    assert "답변 생성" in " ".join(result.changes)


@pytest.mark.asyncio
async def test_rewrite_workflow(workspace_executor, sample_context):
    """재작성 워크플로우 테스트."""
    sample_context.edit_request = "답변을 더 자세히 작성해주세요"

    result = await workspace_executor.execute(WorkflowType.REWRITE, sample_context)

    assert result.workflow == "rewrite"
    assert result.query == sample_context.query
    assert result.answer  # 재작성된 답변
    assert "재작성" in " ".join(result.changes)


@pytest.mark.asyncio
async def test_edit_query_workflow(workspace_executor, sample_context):
    """질의 편집 워크플로우 테스트."""
    result = await workspace_executor.execute(WorkflowType.EDIT_QUERY, sample_context)

    assert result.workflow == "edit_query"
    assert result.query  # 편집된 질문
    assert result.answer == sample_context.answer  # 기존 답변 유지


@pytest.mark.asyncio
async def test_edit_answer_workflow(workspace_executor, sample_context):
    """답변 편집 워크플로우 테스트."""
    sample_context.edit_request = "답변을 수정해주세요"

    result = await workspace_executor.execute(WorkflowType.EDIT_ANSWER, sample_context)

    assert result.workflow == "edit_answer"
    assert result.query == sample_context.query  # 기존 질문 유지
    assert result.answer  # 편집된 답변


@pytest.mark.asyncio
async def test_edit_both_workflow(workspace_executor, sample_context):
    """질의와 답변 모두 편집 워크플로우 테스트."""
    sample_context.edit_request = "둘 다 수정해주세요"

    result = await workspace_executor.execute(WorkflowType.EDIT_BOTH, sample_context)

    assert result.workflow == "edit_both"
    assert result.query  # 편집된 질문
    assert result.answer  # 편집된 답변
    assert len(result.changes) >= 2  # 질의와 답변 둘 다 편집


@pytest.mark.asyncio
async def test_unknown_workflow_raises_error(workspace_executor, sample_context):
    """잘못된 워크플로우 타입 처리."""
    with pytest.raises(ValueError, match="Unknown workflow"):
        # Create invalid workflow type by manipulating the value
        invalid_workflow = Mock()
        invalid_workflow.value = "invalid_workflow"
        await workspace_executor.execute(invalid_workflow, sample_context)


def test_shorten_query(workspace_executor):
    """질의 압축 테스트."""
    long_query = "이것은 매우 긴 질문입니다. " + " ".join(["단어"] * 25)
    short_query = workspace_executor._shorten_query(long_query)

    assert len(short_query.split()) <= 20


def test_get_query_intent(workspace_executor):
    """쿼리 인텐트 생성 테스트."""
    intent = workspace_executor._get_query_intent("target_short", "")
    assert "사실 확인" in intent

    intent = workspace_executor._get_query_intent("target_long", "")
    assert "핵심 요점" in intent

    intent = workspace_executor._get_query_intent("reasoning", "")
    assert "추론" in intent

    intent = workspace_executor._get_query_intent("global_explanation", "")
    assert "전체 내용" in intent


def test_get_query_intent_with_reference(workspace_executor):
    """중복 방지 참조 포함 인텐트 생성."""
    intent = workspace_executor._get_query_intent(
        "target_short", "기존 내용입니다."
    )
    assert "중복 방지" in intent
    assert "기존 내용" in intent


def test_strip_output_tags(workspace_executor):
    """<output> 태그 제거 테스트."""
    text = "<output>테스트 답변</output>"
    result = workspace_executor._strip_output_tags(text)
    assert result == "테스트 답변"

    text = "앞부분 <OUTPUT>중간</OUTPUT> 뒷부분"
    result = workspace_executor._strip_output_tags(text)
    assert "<output>" not in result.lower()
    assert "<OUTPUT>" not in result
