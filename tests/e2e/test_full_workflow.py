"""
전체 워크플로우 E2E 테스트

These tests verify complete end-to-end workflows using mock implementations.
Run with: pytest -m e2e
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from tests.e2e.conftest import MockGeminiAgent


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_qa_workflow(full_workflow_agent: MockGeminiAgent) -> None:
    """
    완전한 Q&A 워크플로우 테스트

    시나리오:
    1. OCR 텍스트 입력
    2. 질의 생성
    3. 답변 생성
    4. 평가 및 재작성
    5. 최종 결과 반환
    """
    # 입력 데이터
    ocr_text = "프랑스의 수도는 무엇인가요?"
    intent = "설명"

    # ===== Step 1: 질의 생성 =====
    query_result = await full_workflow_agent.generate_query(
        ocr_text=ocr_text, intent=intent
    )

    assert query_result is not None
    assert query_result.query
    assert len(query_result.query) > 0

    # ===== Step 2: 답변 생성 =====
    answer_result = await full_workflow_agent.generate_answer(
        query=query_result.query,
        context=ocr_text,
    )

    assert answer_result is not None
    assert answer_result.answer

    # ===== Step 3: 답변 평가 =====
    evaluation = await full_workflow_agent.evaluate_answer(
        query=query_result.query,
        answer=answer_result.answer,
    )

    assert evaluation is not None
    assert 0.0 <= evaluation.score <= 1.0

    # ===== Step 4: 재작성 (점수 낮으면) =====
    if evaluation.score < 0.7:
        rewritten = await full_workflow_agent.rewrite_answer(
            query=query_result.query,
            answer=answer_result.answer,
            feedback=evaluation.feedback,
        )

        assert rewritten is not None
        final_answer = rewritten.answer
    else:
        final_answer = answer_result.answer

    # 최종 검증
    assert final_answer is not None
    assert len(final_answer) > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_caching_across_workflow(full_workflow_agent: MockGeminiAgent) -> None:
    """
    캐싱이 워크플로우 전반에 걸쳐 작동하는지 테스트
    """
    ocr_text = "인공지능이란 무엇인가?"
    intent = "요약"

    # 첫 번째 실행 (캐시 miss)
    result1 = await full_workflow_agent.generate_query(ocr_text, intent)

    # 두 번째 실행 (캐시 hit 기대)
    result2 = await full_workflow_agent.generate_query(ocr_text, intent)

    # 같은 결과
    assert result1.query == result2.query

    # 캐싱 로직이 작동하는지 확인 - 같은 객체가 캐시에서 반환됨
    assert result1 is result2  # Same object from cache


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_recovery_workflow(full_workflow_agent: MockGeminiAgent) -> None:
    """
    에러 복구 시나리오 테스트
    """
    # 잘못된 입력
    invalid_ocr = ""
    intent = "설명"

    # 에러 핸들링 확인
    with pytest.raises(ValueError, match="OCR text cannot be empty"):
        await full_workflow_agent.generate_query(invalid_ocr, intent)

    # 시스템은 계속 작동 (다음 요청 정상)
    valid_result = await full_workflow_agent.generate_query("정상 텍스트", intent)
    assert valid_result is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_workflows(full_workflow_agent: MockGeminiAgent) -> None:
    """
    동시 워크플로우 처리 테스트
    """
    queries = [
        ("질문 1", "설명"),
        ("질문 2", "요약"),
        ("질문 3", "추론"),
    ]

    # 동시 실행
    tasks = [full_workflow_agent.generate_query(ocr, intent) for ocr, intent in queries]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 모두 성공
    assert len(results) == 3
    for result in results:
        assert not isinstance(result, BaseException)
        assert hasattr(result, "query")
        assert result.query


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_batch_processing_workflow(full_workflow_agent: MockGeminiAgent) -> None:
    """
    배치 처리 워크플로우 테스트 (시간 소요)
    """
    # 20개 질의 생성
    batch_size = 20
    queries = [(f"질문 {i}", "설명") for i in range(batch_size)]

    async def process_one(item: tuple[str, str]) -> MagicMock:
        ocr, intent = item
        return await full_workflow_agent.generate_query(ocr, intent)

    # 청크 단위 처리 (5개씩)
    chunk_size = 5
    results = []

    for i in range(0, len(queries), chunk_size):
        chunk = queries[i : i + chunk_size]
        chunk_results = await asyncio.gather(
            *[process_one(item) for item in chunk],
            return_exceptions=True,
        )
        results.extend(chunk_results)
        # 청크 간 딜레이
        await asyncio.sleep(0.1)

    # 모두 처리됨
    assert len(results) == batch_size
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) >= batch_size * 0.9  # 90% 이상 성공


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_intents(full_workflow_agent: MockGeminiAgent) -> None:
    """
    여러 intent에 대한 처리 테스트
    """
    ocr_text = "테스트 문서입니다."
    intents = ["설명", "요약", "분석", "비교"]

    results = []
    for intent in intents:
        result = await full_workflow_agent.generate_query(ocr_text, intent)
        results.append(result)

    assert len(results) == len(intents)
    # 각 intent에 대해 다른 캐시 키 사용됨
    for result in results:
        assert result is not None
        assert result.query
