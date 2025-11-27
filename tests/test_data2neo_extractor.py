"""Tests for Data2NeoExtractor module.

Tests the entity extraction and Neo4j import functionality.
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.features.data2neo_extractor import (
    Data2NeoExtractor,
    Entity,
    EntityType,
    ExtractionResult,
    ExtractedEntitiesSchema,
    Relationship,
    create_data2neo_extractor,
)


@pytest.fixture
def mock_config():
    """Create mock config for testing."""
    config = MagicMock()
    config.data2neo_confidence = 0.7
    config.data2neo_batch_size = 100
    config.enable_data2neo = True
    return config


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    provider = AsyncMock()
    provider.generate_content_async = AsyncMock()
    return provider


@pytest.fixture
def mock_graph_provider():
    """Create mock graph provider."""
    provider = AsyncMock()
    provider.create_nodes = AsyncMock(return_value=1)
    provider.create_relationships = AsyncMock(return_value=1)
    return provider


class TestEntity:
    """Tests for Entity model."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(
            id="person_john_doe",
            type=EntityType.PERSON,
            properties={"name": "John Doe", "role": "Engineer"},
            confidence=0.9,
        )
        assert entity.id == "person_john_doe"
        assert entity.type == EntityType.PERSON
        assert entity.properties["name"] == "John Doe"
        assert entity.confidence == 0.9

    def test_entity_default_confidence(self):
        """Test entity default confidence value."""
        entity = Entity(
            id="org_acme",
            type=EntityType.ORGANIZATION,
            properties={"name": "Acme Corp"},
        )
        assert entity.confidence == 1.0

    def test_entity_types(self):
        """Test all entity types."""
        assert EntityType.PERSON.value == "Person"
        assert EntityType.ORGANIZATION.value == "Organization"
        assert EntityType.DOCUMENT_RULE.value == "DocumentRule"
        assert EntityType.DOCUMENT.value == "Document"
        assert EntityType.CHUNK.value == "Chunk"


class TestRelationship:
    """Tests for Relationship model."""

    def test_relationship_creation(self):
        """Test basic relationship creation."""
        rel = Relationship(
            from_id="person_john",
            to_id="org_acme",
            type="WORKS_AT",
            properties={"since": "2020"},
        )
        assert rel.from_id == "person_john"
        assert rel.to_id == "org_acme"
        assert rel.type == "WORKS_AT"
        assert rel.properties["since"] == "2020"


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_extraction_result_default(self):
        """Test default extraction result."""
        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []
        assert result.document_id is None
        assert result.chunk_count == 0

    def test_extraction_result_with_data(self):
        """Test extraction result with data."""
        entity = Entity(id="test", type=EntityType.PERSON, properties={})
        rel = Relationship(from_id="a", to_id="b", type="REL")
        result = ExtractionResult(
            entities=[entity],
            relationships=[rel],
            document_id="doc_1",
            chunk_count=3,
        )
        assert len(result.entities) == 1
        assert len(result.relationships) == 1
        assert result.document_id == "doc_1"
        assert result.chunk_count == 3


class TestExtractedEntitiesSchema:
    """Tests for ExtractedEntitiesSchema parsing."""

    def test_schema_parsing(self):
        """Test schema parsing from dict."""
        data = {
            "persons": [{"id": "p1", "name": "John", "role": "Manager"}],
            "organizations": [{"id": "o1", "name": "Acme", "type": "company"}],
            "rules": [{"id": "r1", "text": "Rule text", "priority": "high"}],
            "relationships": [{"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"}],
        }
        schema = ExtractedEntitiesSchema.model_validate(data)
        assert len(schema.persons) == 1
        assert len(schema.organizations) == 1
        assert len(schema.rules) == 1
        assert len(schema.relationships) == 1

    def test_schema_empty(self):
        """Test schema with empty data."""
        schema = ExtractedEntitiesSchema()
        assert schema.persons == []
        assert schema.organizations == []
        assert schema.rules == []
        assert schema.relationships == []

    def test_schema_null_values(self):
        """Test schema handles null values."""
        data = {
            "persons": None,
            "organizations": None,
            "rules": None,
            "relationships": None,
        }
        schema = ExtractedEntitiesSchema.model_validate(data)
        assert schema.persons == []
        assert schema.organizations == []


class TestData2NeoExtractor:
    """Tests for Data2NeoExtractor class."""

    def test_extractor_initialization(self, mock_config):
        """Test extractor initialization."""
        extractor = Data2NeoExtractor(config=mock_config)
        assert extractor.confidence_threshold == 0.7
        assert extractor.batch_size == 100

    def test_chunk_text_short(self, mock_config):
        """Test chunking short text."""
        extractor = Data2NeoExtractor(config=mock_config)
        text = "Short text"
        chunks = extractor._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long(self, mock_config):
        """Test chunking long text."""
        extractor = Data2NeoExtractor(config=mock_config)
        text = "Paragraph one.\n\n" * 100  # Long text
        chunks = extractor._chunk_text(text, chunk_size=100)
        assert len(chunks) > 1

    def test_generate_entity_id(self, mock_config):
        """Test entity ID generation."""
        extractor = Data2NeoExtractor(config=mock_config)
        entity_id = extractor._generate_entity_id("person", "John Doe")
        assert entity_id == "person_john_doe"

    def test_generate_entity_id_special_chars(self, mock_config):
        """Test entity ID generation with special characters."""
        extractor = Data2NeoExtractor(config=mock_config)
        entity_id = extractor._generate_entity_id("organization", "Acme, Inc.")
        assert "_" in entity_id
        assert "," not in entity_id

    def test_parse_extraction_response_valid(self, mock_config):
        """Test parsing valid JSON response."""
        extractor = Data2NeoExtractor(config=mock_config)
        response = """
        {
            "persons": [{"id": "p1", "name": "John"}],
            "organizations": [],
            "rules": [],
            "relationships": []
        }
        """
        result = extractor._parse_extraction_response(response)
        assert len(result.persons) == 1
        assert result.persons[0]["name"] == "John"

    def test_parse_extraction_response_invalid(self, mock_config):
        """Test parsing invalid response."""
        extractor = Data2NeoExtractor(config=mock_config)
        response = "This is not JSON"
        result = extractor._parse_extraction_response(response)
        assert len(result.persons) == 0

    def test_convert_to_entities(self, mock_config):
        """Test converting schema to entities."""
        extractor = Data2NeoExtractor(config=mock_config)
        schema = ExtractedEntitiesSchema(
            persons=[
                {"id": "p1", "name": "John", "role": "Manager", "confidence": 0.9}
            ],
            organizations=[{"id": "o1", "name": "Acme", "type": "company"}],
            rules=[{"text": "Rule 1", "priority": "high"}],
            relationships=[{"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"}],
        )
        result = extractor._convert_to_entities(schema, "doc_1")
        assert len(result.entities) == 3  # 1 person + 1 org + 1 rule
        assert len(result.relationships) == 1

    def test_convert_to_entities_confidence_filter(self, mock_config):
        """Test confidence threshold filtering."""
        mock_config.data2neo_confidence = 0.8
        extractor = Data2NeoExtractor(config=mock_config)
        schema = ExtractedEntitiesSchema(
            persons=[
                {"id": "p1", "name": "John", "confidence": 0.9},
                {"id": "p2", "name": "Jane", "confidence": 0.5},  # Below threshold
            ],
        )
        result = extractor._convert_to_entities(schema, "doc_1")
        # Only one person should pass the confidence filter
        assert len([e for e in result.entities if e.type == EntityType.PERSON]) == 1

    @pytest.mark.asyncio
    async def test_extract_entities_no_provider(self, mock_config):
        """Test extraction without LLM provider."""
        extractor = Data2NeoExtractor(config=mock_config, llm_provider=None)
        result = await extractor.extract_entities("Test text", "doc_1")
        assert len(result.entities) == 0
        assert result.document_id == "doc_1"

    @pytest.mark.asyncio
    async def test_extract_entities_with_provider(self, mock_config, mock_llm_provider):
        """Test extraction with LLM provider."""
        mock_llm_provider.generate_content_async.return_value = MagicMock(
            content='{"persons": [{"id": "p1", "name": "John"}], "organizations": [], "rules": [], "relationships": []}'
        )
        extractor = Data2NeoExtractor(
            config=mock_config, llm_provider=mock_llm_provider
        )
        await extractor.extract_entities("John works at Acme", "doc_1")
        assert mock_llm_provider.generate_content_async.called
        # Result depends on parsing

    @pytest.mark.asyncio
    async def test_import_to_graph_no_provider(self, mock_config):
        """Test import without graph provider."""
        extractor = Data2NeoExtractor(config=mock_config, graph_provider=None)
        result = ExtractionResult(
            entities=[
                Entity(id="p1", type=EntityType.PERSON, properties={"name": "John"})
            ],
        )
        counts = await extractor.import_to_graph(result)
        assert counts["nodes"] == 0
        assert counts["relationships"] == 0

    @pytest.mark.asyncio
    async def test_import_to_graph_with_provider(
        self, mock_config, mock_graph_provider
    ):
        """Test import with graph provider."""
        extractor = Data2NeoExtractor(
            config=mock_config, graph_provider=mock_graph_provider
        )
        result = ExtractionResult(
            entities=[
                Entity(id="p1", type=EntityType.PERSON, properties={"name": "John"}),
                Entity(
                    id="o1", type=EntityType.ORGANIZATION, properties={"name": "Acme"}
                ),
            ],
            relationships=[
                Relationship(from_id="p1", to_id="o1", type="WORKS_AT"),
            ],
        )
        counts = await extractor.import_to_graph(result)
        assert mock_graph_provider.create_nodes.called
        assert counts["nodes"] > 0

    @pytest.mark.asyncio
    async def test_extract_and_import(
        self, mock_config, mock_llm_provider, mock_graph_provider
    ):
        """Test full extraction and import pipeline."""
        llm_response = {
            "persons": [{"id": "p1", "name": "John", "role": "Manager"}],
            "organizations": [{"id": "o1", "name": "Acme"}],
            "rules": [],
            "relationships": [{"from_id": "p1", "to_id": "o1", "type": "WORKS_AT"}],
        }
        mock_llm_provider.generate_content_async.return_value = MagicMock(
            content=json.dumps(llm_response)
        )
        extractor = Data2NeoExtractor(
            config=mock_config,
            llm_provider=mock_llm_provider,
            graph_provider=mock_graph_provider,
        )
        result = await extractor.extract_and_import(
            "John from Acme", "/path/to/doc.txt"
        )
        assert result.document_id is not None
        assert mock_graph_provider.create_nodes.called


class TestCreateData2NeoExtractor:
    """Tests for factory function."""

    @pytest.mark.asyncio
    async def test_create_extractor_disabled(self, mock_config):
        """Test factory with data2neo disabled."""
        mock_config.enable_data2neo = False
        extractor = await create_data2neo_extractor(mock_config)
        assert extractor.llm_provider is None
        assert extractor.graph_provider is None

    @pytest.mark.asyncio
    async def test_create_extractor_with_providers(
        self, mock_config, mock_llm_provider, mock_graph_provider
    ):
        """Test factory with provided providers."""
        extractor = await create_data2neo_extractor(
            mock_config,
            llm_provider=mock_llm_provider,
            graph_provider=mock_graph_provider,
        )
        assert extractor.llm_provider == mock_llm_provider
        assert extractor.graph_provider == mock_graph_provider
