"""Additional tests for src/features/data2neo_extractor.py to improve coverage.

Targets:
- Entity extraction edge cases
- JSON parsing error handling
- Chunk processing
- Graph import logic
- Confidence thresholding
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import pytest

from src.features.data2neo_extractor import (
    Data2NeoExtractor,
    Entity,
    EntityType,
    ExtractionResult,
    Relationship,
    create_data2neo_extractor,
)


class TestData2NeoExtractorInit:
    """Test Data2NeoExtractor initialization."""

    def test_init_with_config_values(self) -> None:
        """Test initialization with config values."""
        config = Mock()
        config.data2neo_confidence = 0.8
        config.data2neo_batch_size = 50
        config.data2neo_temperature = 0.2

        extractor = Data2NeoExtractor(config=config)

        assert extractor.confidence_threshold == 0.8
        assert extractor.batch_size == 50
        assert extractor.extraction_temperature == 0.2

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        config = Mock(spec=[])  # No attributes

        extractor = Data2NeoExtractor(config=config)

        assert extractor.confidence_threshold == 0.7
        assert extractor.batch_size == 100
        assert extractor.extraction_temperature == 0.1

    def test_extraction_prompt_built(self) -> None:
        """Test that extraction prompt is built on init."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        assert len(extractor._extraction_prompt) > 0
        assert "entity extraction" in extractor._extraction_prompt.lower()


class TestChunkText:
    """Test text chunking functionality."""

    def test_chunk_text_short_text(self) -> None:
        """Test chunking text shorter than chunk size."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        text = "짧은 텍스트"
        chunks = extractor._chunk_text(text, chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long_text_with_paragraphs(self) -> None:
        """Test chunking long text with paragraph boundaries."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        paragraphs = [f"단락 {i}" * 100 for i in range(10)]
        text = "\n\n".join(paragraphs)

        chunks = extractor._chunk_text(text, chunk_size=1000)

        assert len(chunks) > 1
        # Each chunk should be reasonably sized
        for chunk in chunks:
            assert len(chunk) <= 1100  # Allow some overflow

    def test_chunk_text_very_long_paragraph(self) -> None:
        """Test chunking with very long paragraph (no breaks)."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        text = "A" * 5000
        chunks = extractor._chunk_text(text, chunk_size=1000)

        assert len(chunks) == 5
        for chunk in chunks:
            assert len(chunk) == 1000


class TestGenerateEntityID:
    """Test entity ID generation."""

    def test_generate_entity_id_normalizes_name(self) -> None:
        """Test entity ID generation normalizes names."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        entity_id = extractor._generate_entity_id("Person", "홍길동")

        assert entity_id.startswith("person_")
        assert "_" in entity_id

    def test_generate_entity_id_handles_special_chars(self) -> None:
        """Test entity ID handles special characters."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        entity_id = extractor._generate_entity_id("Organization", "삼성@전자(주)")

        assert entity_id.startswith("organization_")
        # Special chars should be replaced with underscores
        assert "@" not in entity_id
        assert "(" not in entity_id


class TestParseExtractionResponse:
    """Test LLM response parsing."""

    def test_parse_extraction_response_valid_json(self) -> None:
        """Test parsing valid JSON response."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = json.dumps({
            "persons": [{"id": "p1", "name": "홍길동", "role": "CEO"}],
            "organizations": [{"id": "o1", "name": "삼성전자"}],
            "rules": [],
            "relationships": [],
        })

        result = extractor._parse_extraction_response(response)

        assert len(result.persons) == 1
        assert result.persons[0]["name"] == "홍길동"
        assert len(result.organizations) == 1

    def test_parse_extraction_response_json_in_text(self) -> None:
        """Test parsing JSON embedded in text."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = """Here is the result:
        {"persons": [{"id": "p1", "name": "김철수"}], "organizations": [], "rules": [], "relationships": []}
        That's all."""

        result = extractor._parse_extraction_response(response)

        assert len(result.persons) == 1
        assert result.persons[0]["name"] == "김철수"

    def test_parse_extraction_response_with_markdown_bold(self) -> None:
        """Test parsing JSON with markdown bold markers."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = """{
            **"persons"**: [{"id": "p1", "name": "홍길동"}],
            "organizations": [],
            "rules": [],
            "relationships": []
        }"""

        result = extractor._parse_extraction_response(response)

        # Bold markers should be removed and parse successfully
        assert len(result.persons) == 1

    def test_parse_extraction_response_with_list_markers(self) -> None:
        """Test parsing JSON with markdown list markers."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = """{
            - "persons": [{"id": "p1", "name": "김철수"}],
            - "organizations": [],
            - "rules": [],
            - "relationships": []
        }"""

        result = extractor._parse_extraction_response(response)

        # List markers should be removed
        assert len(result.persons) == 1

    def test_parse_extraction_response_invalid_json(self) -> None:
        """Test parsing invalid JSON returns empty result."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = "This is not JSON at all"

        result = extractor._parse_extraction_response(response)

        assert len(result.persons) == 0
        assert len(result.organizations) == 0

    def test_parse_extraction_response_no_json_object(self) -> None:
        """Test response without JSON object."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        response = "No curly braces here"

        result = extractor._parse_extraction_response(response)

        assert len(result.persons) == 0


class TestConvertToEntities:
    """Test conversion from parsed schema to Entity objects."""

    def test_convert_to_entities_persons(self) -> None:
        """Test converting person entities."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        from src.features.data2neo_extractor import ExtractedEntitiesSchema

        schema = ExtractedEntitiesSchema(
            persons=[
                {"id": "p1", "name": "홍길동", "role": "CEO", "confidence": 0.9}
            ],
            organizations=[],
            rules=[],
            relationships=[],
        )

        result = extractor._convert_to_entities(schema, "doc1")

        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.type == EntityType.PERSON
        assert entity.id == "p1"
        assert entity.properties["name"] == "홍길동"
        assert entity.confidence == 0.9

    def test_convert_to_entities_organizations(self) -> None:
        """Test converting organization entities."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        from src.features.data2neo_extractor import ExtractedEntitiesSchema

        schema = ExtractedEntitiesSchema(
            persons=[],
            organizations=[
                {"id": "o1", "name": "삼성전자", "type": "대기업", "confidence": 0.85}
            ],
            rules=[],
            relationships=[],
        )

        result = extractor._convert_to_entities(schema, "doc1")

        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.type == EntityType.ORGANIZATION
        assert entity.properties["name"] == "삼성전자"

    def test_convert_to_entities_rules(self) -> None:
        """Test converting rule entities."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        from src.features.data2neo_extractor import ExtractedEntitiesSchema

        schema = ExtractedEntitiesSchema(
            persons=[],
            organizations=[],
            rules=[
                {
                    "id": "r1",
                    "text": "모든 직원은 출근해야 합니다",
                    "priority": "high",
                }
            ],
            relationships=[],
        )

        result = extractor._convert_to_entities(schema, "doc1")

        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.type == EntityType.DOCUMENT_RULE
        assert entity.properties["text"] == "모든 직원은 출근해야 합니다"

    def test_convert_to_entities_filters_low_confidence(self) -> None:
        """Test filtering entities below confidence threshold."""
        config = Mock()
        config.data2neo_confidence = 0.8
        extractor = Data2NeoExtractor(config=config)

        from src.features.data2neo_extractor import ExtractedEntitiesSchema

        schema = ExtractedEntitiesSchema(
            persons=[
                {"id": "p1", "name": "높은신뢰", "confidence": 0.9},
                {"id": "p2", "name": "낮은신뢰", "confidence": 0.5},
            ],
            organizations=[],
            rules=[],
            relationships=[],
        )

        result = extractor._convert_to_entities(schema, "doc1")

        # Only high confidence entity should remain
        assert len(result.entities) == 1
        assert result.entities[0].properties["name"] == "높은신뢰"

    def test_convert_to_entities_skips_empty_names(self) -> None:
        """Test skipping entities without names."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        from src.features.data2neo_extractor import ExtractedEntitiesSchema

        schema = ExtractedEntitiesSchema(
            persons=[
                {"id": "p1", "name": "", "role": "CEO"},
                {"id": "p2", "name": "유효한이름", "role": "CTO"},
            ],
            organizations=[],
            rules=[],
            relationships=[],
        )

        result = extractor._convert_to_entities(schema, "doc1")

        assert len(result.entities) == 1
        assert result.entities[0].properties["name"] == "유효한이름"


class TestBuildRelationships:
    """Test relationship building."""

    def test_build_relationships_valid(self) -> None:
        """Test building valid relationships."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        relationships = [
            {"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"},
            {"from_id": "p2", "to_id": "o1", "type": "MANAGES"},
        ]

        result = extractor._build_relationships(relationships)

        assert len(result) == 2
        assert result[0].from_id == "p1"
        assert result[0].type == "WORKS_AT"

    def test_build_relationships_skips_invalid(self) -> None:
        """Test skipping relationships with missing IDs."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config)

        relationships = [
            {"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"},
            {"from_id": "", "to_id": "o1", "type": "INVALID"},
            {"from_id": "p2", "to_id": "", "type": "ALSO_INVALID"},
        ]

        result = extractor._build_relationships(relationships)

        assert len(result) == 1


class TestExtractEntities:
    """Test entity extraction from OCR text."""

    @pytest.mark.asyncio
    async def test_extract_entities_no_llm_provider(self) -> None:
        """Test extraction without LLM provider."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config, llm_provider=None)

        result = await extractor.extract_entities("OCR 텍스트", "doc1")

        assert result.document_id == "doc1"
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_extract_entities_success(self) -> None:
        """Test successful entity extraction."""
        config = Mock()
        mock_llm = Mock()
        mock_llm.generate_content_async = AsyncMock()
        mock_llm.generate_content_async.return_value = Mock(
            content=json.dumps({
                "persons": [{"id": "p1", "name": "홍길동", "role": "CEO"}],
                "organizations": [{"id": "o1", "name": "테스트회사"}],
                "rules": [],
                "relationships": [{"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"}],
            })
        )

        extractor = Data2NeoExtractor(config=config, llm_provider=mock_llm)

        result = await extractor.extract_entities("OCR 텍스트", "doc1")

        assert len(result.entities) >= 2
        assert len(result.relationships) == 1

    @pytest.mark.asyncio
    async def test_extract_entities_with_chunks(self) -> None:
        """Test extraction with text chunking."""
        config = Mock()
        mock_llm = Mock()
        mock_llm.generate_content_async = AsyncMock()
        mock_llm.generate_content_async.return_value = Mock(
            content=json.dumps({
                "persons": [{"id": "p1", "name": "김철수"}],
                "organizations": [],
                "rules": [],
                "relationships": [],
            })
        )

        extractor = Data2NeoExtractor(config=config, llm_provider=mock_llm)

        # Long text to trigger chunking
        long_text = "A" * 10000

        result = await extractor.extract_entities(long_text, "doc1")

        # Should have called LLM multiple times
        assert mock_llm.generate_content_async.call_count > 1

    @pytest.mark.asyncio
    async def test_extract_entities_deduplicates(self) -> None:
        """Test that duplicate entities are deduplicated."""
        config = Mock()
        mock_llm = Mock()

        # Return same entity twice
        mock_llm.generate_content_async = AsyncMock()
        mock_llm.generate_content_async.side_effect = [
            Mock(
                content=json.dumps({
                    "persons": [{"id": "p1", "name": "홍길동"}],
                    "organizations": [],
                    "rules": [],
                    "relationships": [],
                })
            ),
            Mock(
                content=json.dumps({
                    "persons": [{"id": "p1", "name": "홍길동"}],
                    "organizations": [],
                    "rules": [],
                    "relationships": [],
                })
            ),
        ]

        extractor = Data2NeoExtractor(config=config, llm_provider=mock_llm)

        # Long text to trigger chunking
        result = await extractor.extract_entities("A" * 10000, "doc1")

        # Should have only one entity despite appearing in both chunks
        entity_ids = [e.id for e in result.entities]
        assert len(entity_ids) == len(set(entity_ids))

    @pytest.mark.asyncio
    async def test_extract_entities_handles_llm_error(self) -> None:
        """Test handling LLM errors during extraction."""
        config = Mock()
        mock_llm = Mock()
        mock_llm.generate_content_async = AsyncMock()
        mock_llm.generate_content_async.side_effect = ValueError("LLM 오류")

        extractor = Data2NeoExtractor(config=config, llm_provider=mock_llm)

        result = await extractor.extract_entities("OCR 텍스트", "doc1")

        # Should return empty result on error
        assert len(result.entities) == 0


class TestImportToGraph:
    """Test graph import functionality."""

    @pytest.mark.asyncio
    async def test_import_to_graph_no_provider(self) -> None:
        """Test import without graph provider."""
        config = Mock()
        extractor = Data2NeoExtractor(config=config, graph_provider=None)

        result = ExtractionResult(
            entities=[
                Entity(
                    id="p1",
                    type=EntityType.PERSON,
                    properties={"name": "홍길동"},
                )
            ],
            relationships=[],
            document_id="doc1",
        )

        counts = await extractor.import_to_graph(result)

        assert counts["nodes"] == 0
        assert counts["relationships"] == 0

    @pytest.mark.asyncio
    async def test_import_to_graph_success(self) -> None:
        """Test successful graph import."""
        config = Mock()
        mock_graph = Mock()
        mock_graph.create_nodes = AsyncMock(return_value=2)
        mock_graph.create_relationships = AsyncMock(return_value=1)

        extractor = Data2NeoExtractor(config=config, graph_provider=mock_graph)

        result = ExtractionResult(
            entities=[
                Entity(
                    id="p1",
                    type=EntityType.PERSON,
                    properties={"name": "홍길동"},
                ),
                Entity(
                    id="o1",
                    type=EntityType.ORGANIZATION,
                    properties={"name": "회사"},
                ),
            ],
            relationships=[
                Relationship(from_id="p1", to_id="o1", type="WORKS_AT")
            ],
            document_id="doc1",
        )

        counts = await extractor.import_to_graph(result)

        assert counts["nodes"] == 2
        assert counts["relationships"] == 1

    @pytest.mark.asyncio
    async def test_import_to_graph_handles_node_error(self) -> None:
        """Test handling node creation errors."""
        config = Mock()
        mock_graph = Mock()
        mock_graph.create_nodes = AsyncMock(side_effect=ValueError("생성 실패"))

        extractor = Data2NeoExtractor(config=config, graph_provider=mock_graph)

        result = ExtractionResult(
            entities=[
                Entity(
                    id="p1",
                    type=EntityType.PERSON,
                    properties={"name": "홍길동"},
                )
            ],
            relationships=[],
            document_id="doc1",
        )

        counts = await extractor.import_to_graph(result)

        # Should handle error gracefully
        assert counts["nodes"] == 0


class TestExtractAndImport:
    """Test full extraction and import pipeline."""

    @pytest.mark.asyncio
    async def test_extract_and_import_creates_document_node(self) -> None:
        """Test that document node is created."""
        config = Mock()
        mock_graph = Mock()
        mock_graph.create_nodes = AsyncMock(return_value=1)

        extractor = Data2NeoExtractor(
            config=config,
            llm_provider=None,
            graph_provider=mock_graph,
        )

        result = await extractor.extract_and_import("OCR", "/path/to/doc.pdf")

        # Should have tried to create document node
        mock_graph.create_nodes.assert_called()
        call_args = mock_graph.create_nodes.call_args
        assert call_args[1]["label"] == "Document"

    @pytest.mark.asyncio
    async def test_extract_and_import_handles_document_creation_error(self) -> None:
        """Test handling document node creation error."""
        config = Mock()
        mock_graph = Mock()
        mock_graph.create_nodes = AsyncMock(side_effect=ValueError("오류"))

        extractor = Data2NeoExtractor(
            config=config,
            llm_provider=None,
            graph_provider=mock_graph,
        )

        # Should not raise exception
        result = await extractor.extract_and_import("OCR", "/path/to/doc.pdf")

        assert result.document_id is not None


class TestCreateData2NeoExtractor:
    """Test factory function."""

    @pytest.mark.asyncio
    async def test_create_data2neo_extractor_disabled(self) -> None:
        """Test factory when data2neo is disabled."""
        config = Mock()
        config.enable_data2neo = False

        extractor = await create_data2neo_extractor(config)

        assert extractor.llm_provider is None
        assert extractor.graph_provider is None

    @pytest.mark.asyncio
    async def test_create_data2neo_extractor_with_providers(self) -> None:
        """Test factory with provided providers."""
        config = Mock()
        mock_llm = Mock()
        mock_graph = Mock()

        extractor = await create_data2neo_extractor(
            config, llm_provider=mock_llm, graph_provider=mock_graph
        )

        assert extractor.llm_provider == mock_llm
        assert extractor.graph_provider == mock_graph
