from __future__ import annotations

from typing import Any

from PIL import Image

from src.qa.rag_system import QAKnowledgeGraph


class MultimodalUnderstanding:
    """이미지 구조 분석으로 메타데이터 자동 생성 (OCR은 사용자 직접 입력)."""

    def __init__(self, kg: QAKnowledgeGraph):
        """Initialize the multimodal understanding system.

        Args:
            kg: QAKnowledgeGraph instance for graph queries.
        """
        self.kg = kg

    def analyze_image_deep(self, image_path: str) -> dict[str, Any]:
        """이미지 심층 분석: 구조 분석, 텍스트 밀도/토픽 추출 후 그래프 저장.

        Note: OCR 텍스트는 사용자가 직접 입력합니다 (자동 추출 비활성화됨).

        Args:
            image_path: 분석할 이미지 파일 경로.

        Returns:
            dict: 텍스트 밀도, 주제 목록, 테이블/차트 여부 등 메타데이터.
        """
        with Image.open(image_path) as img:
            # 1. 구조 분석 (표/그래프 감지)
            has_table = self._detect_table(img)
            has_chart = self._detect_chart(img)

            # 2. 텍스트 밀도 계산 (이미지 크기 기반)
            text_density = 0.0  # OCR 없이는 계산 불가, 기본값 사용

        # 3. 주제 추출 (OCR 없이는 빈 리스트 반환)
        topics: list[str] = []

        metadata = {
            "path": image_path,
            "has_table_chart": has_table or has_chart,
            "text_density": text_density,
            "topics": topics,
            "extracted_text": "",  # OCR 비활성화됨
        }

        # 5. Neo4j에 저장 (실패해도 분석 결과는 반환)
        try:
            graph_session = getattr(self.kg, "graph_session", None)
            if graph_session is None:
                graph = getattr(self.kg, "_graph", None)
                if graph is None:
                    return metadata
                session_ctx = graph.session
            else:
                session_ctx = graph_session

            with session_ctx() as session:
                if session is None:
                    return metadata
                session.run(
                    """
                    MERGE (img:ImageMeta {path: $path})
                    SET img.has_table_chart = $has_table_chart,
                        img.text_density = $text_density,
                        img.topics = $topics,
                        img.analyzed_at = datetime()
                    """,
                    **metadata,
                )
        except Exception:
            pass

        return metadata

    def _detect_table(self, _img: Image.Image) -> bool:
        """표 감지 (placeholder 휴리스틱)."""
        # 실제 구현 시 CV 모델 적용
        return False

    def _detect_chart(self, _img: Image.Image) -> bool:
        """그래프 감지 (placeholder)."""
        # 실제 구현 시 색상 히스토그램/선 패턴 감지 등 적용
        return False
