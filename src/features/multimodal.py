"""Multimodal Image Understanding module.

Analyzes image structure (tables, charts) and performs OCR using Gemini Vision.
Stores analysis results in Neo4j for downstream processing.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

if TYPE_CHECKING:
    from src.core.interfaces import LLMProvider
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# OCR 프롬프트 (한글 증권 리포트에 최적화)
OCR_PROMPT = """이 이미지의 모든 텍스트를 정확히 추출해주세요.

규칙:
- 표가 있다면 구조를 유지해주세요
- 줄바꿈과 단락 구분을 유지해주세요
- 숫자, 특수문자, 퍼센트(%)를 정확히 인식해주세요
- 한글과 영문을 정확히 구분해주세요"""


class MultimodalUnderstanding:
    """이미지 구조 분석 및 Gemini Vision OCR로 텍스트 추출."""

    def __init__(
        self,
        kg: QAKnowledgeGraph | None = None,
        llm_provider: LLMProvider | None = None,
    ):
        """Initialize the multimodal understanding system.

        Args:
            kg: QAKnowledgeGraph instance for graph queries (optional).
            llm_provider: LLM provider for Vision OCR (optional).
        """
        self.kg = kg
        self.llm_provider = llm_provider

    async def analyze_image_deep(self, image_path: str) -> dict[str, Any]:
        """이미지 심층 분석: Gemini Vision OCR + 구조 분석 + 메타데이터 추출.

        Args:
            image_path: 분석할 이미지 파일 경로.

        Returns:
            dict: 추출된 텍스트, 텍스트 밀도, 주제, 테이블/차트 여부 등.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # 1. 이미지 크기 정보 추출
        with Image.open(image_path) as img:
            width, height = img.size
            area = width * height

        # 2. Gemini Vision OCR로 텍스트 추출
        extracted_text = ""
        if self.llm_provider is not None:
            try:
                image_data = path.read_bytes()
                mime_type = self._get_mime_type(path)
                extracted_text = await self.llm_provider.generate_vision_content_async(
                    image_data, mime_type, OCR_PROMPT
                )
                logger.info(
                    "OCR completed: %d chars extracted from %s",
                    len(extracted_text),
                    path.name,
                )
            except Exception as e:
                logger.error("OCR failed for %s: %s", image_path, e)

        # 3. 텍스트 밀도 계산 (글자수 / 이미지 면적 * 1000000)
        text_density = (len(extracted_text) / area * 1_000_000) if area > 0 else 0.0

        # 4. 주제/키워드 추출
        topics = self._extract_topics(extracted_text)

        # 5. 표/차트 감지 (텍스트 기반 휴리스틱)
        has_table_chart = self._detect_table_chart(extracted_text)

        metadata: dict[str, Any] = {
            "path": image_path,
            "extracted_text": extracted_text,
            "text_density": round(text_density, 2),
            "topics": topics,
            "has_table_chart": has_table_chart,
            "image_width": width,
            "image_height": height,
        }

        # 6. Neo4j에 저장 (실패해도 분석 결과는 반환)
        self._save_to_neo4j(metadata)

        return metadata

    def _get_mime_type(self, path: Path) -> str:
        """파일 확장자로 MIME 타입 결정."""
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(suffix, "image/png")

    def _extract_topics(self, text: str) -> list[str]:
        """텍스트에서 주요 키워드/주제 추출."""
        if not text:
            return []

        # 증권 리포트 관련 키워드 패턴
        patterns = [
            r"(매출액|영업이익|순이익|EPS|PER|PBR|ROE|ROA)",
            r"(목표주가|투자의견|Buy|Hold|Sell|시가총액)",
            r"(\d{4}년?\s*\d{1,2}분기|\d{1,2}Q\d{2})",
            r"(컨센서스|실적|전망|성장|증가|감소)",
        ]

        topics = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            topics.update(matches)

        return list(topics)[:10]  # 최대 10개

    def _detect_table_chart(self, text: str) -> bool:
        """텍스트에서 표/차트 존재 여부 감지."""
        if not text:
            return False

        # 표 관련 패턴
        table_patterns = [
            r"\d+\s+\d+\s+\d+",  # 숫자 열
            r"(단위|원|억|조|%)",
            r"(구분|항목|합계|소계)",
        ]

        return any(re.search(pattern, text) for pattern in table_patterns)

    def _save_to_neo4j(self, metadata: dict[str, Any]) -> None:
        """메타데이터를 Neo4j에 저장."""
        if self.kg is None:
            return

        try:
            graph_session = getattr(self.kg, "graph_session", None)
            if graph_session is None:
                graph = getattr(self.kg, "_graph", None)
                if graph is None:
                    return
                session_ctx = graph.session
            else:
                session_ctx = graph_session

            with session_ctx() as session:
                if session is None:
                    return
                session.run(
                    """
                    MERGE (img:ImageMeta {path: $path})
                    SET img.has_table_chart = $has_table_chart,
                        img.text_density = $text_density,
                        img.topics = $topics,
                        img.analyzed_at = datetime()
                    """,
                    path=metadata["path"],
                    has_table_chart=metadata["has_table_chart"],
                    text_density=metadata["text_density"],
                    topics=metadata["topics"],
                )
        except Exception as e:
            logger.debug("Failed to save to Neo4j: %s", e)
