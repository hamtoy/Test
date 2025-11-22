from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from PIL import Image
import pytesseract

from qa_rag_system import QAKnowledgeGraph


class MultimodalUnderstanding:
    """
    이미지 OCR + 구조 분석으로 메타데이터 자동 생성
    """

    def __init__(self, kg: QAKnowledgeGraph):
        self.kg = kg

    def analyze_image_deep(self, image_path: str) -> Dict[str, Any]:
        """
        이미지 심층 분석: OCR, 표/그래프 감지, 텍스트 밀도/토픽 추출 후 그래프 저장.
        """

        img = Image.open(image_path)

        # 1. OCR로 텍스트 추출
        text = pytesseract.image_to_string(img, lang="kor+eng")

        # 2. 구조 분석 (표/그래프 감지)
        has_table = self._detect_table(img)
        has_chart = self._detect_chart(img)

        # 3. 텍스트 밀도 계산
        text_density = (len(text.strip()) / (img.width * img.height)) * 10000

        # 4. 주제 추출 (NLP - 단순 빈도 기반)
        topics = self._extract_topics(text)

        metadata = {
            "path": image_path,
            "has_table_chart": has_table or has_chart,
            "text_density": text_density,
            "topics": topics,
            "extracted_text": text[:1000],  # 샘플만 저장
        }

        # 5. Neo4j에 저장 (실패해도 분석 결과는 반환)
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
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

    def _detect_table(self, img: Image.Image) -> bool:
        """표 감지 (placeholder 휴리스틱)."""
        # 실제 구현 시 CV 모델 적용
        return False

    def _detect_chart(self, img: Image.Image) -> bool:
        """그래프 감지 (placeholder)."""
        # 실제 구현 시 색상 히스토그램/선 패턴 감지 등 적용
        return False

    def _extract_topics(self, text: str) -> List[str]:
        """주제 추출 (단순 빈도 기반)."""

        words = [w for w in text.split() if len(w) > 2]
        common = Counter(words).most_common(5)
        return [w for w, _ in common]
