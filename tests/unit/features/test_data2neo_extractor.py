"""Tests for Data2NeoExtractor module.

Tests the entity extraction and Neo4j import functionality.
Tests cover:
- Entity model creation and validation
- Entity extraction from OCR text
- Confidence threshold filtering
- Graph writing (mocked)
- Error handling
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from jinja2 import Environment, DictLoader

from src.config import AppConfig
from src.features.data2neo_extractor import (
    Entity,
    EntityType,
    ExtractedEntitiesSchema,
    create_data2neo_extractor,
)
from src.features.data2neo_extractor import (
    Data2NeoExtractor as FeaturesData2NeoExtractor,
)
from src.features.data2neo_extractor import ExtractionResult as FeaturesExtractionResult
from src.features.data2neo_extractor import Relationship as FeaturesRelationship
from src.graph.data2neo_extractor import Data2NeoExtractor
from src.graph.entities import (
    DateEntity,
    DocumentRule,
    ExtractionResult,
    Organization,
    Person,
    Relationship,
)


@pytest.fixture
def mock_config() -> Any:
    """Create mock config for testing."""
    config = MagicMock()
    config.data2neo_confidence = 0.7
    config.data2neo_batch_size = 100
    config.enable_data2neo = True
    return config


@pytest.fixture
def mock_llm_provider() -> Any:
    """Create mock LLM provider."""
    provider = AsyncMock()
    provider.generate_content_async = AsyncMock()
    return provider


@pytest.fixture
def mock_graph_provider() -> Any:
    """Create mock graph provider."""
    provider = AsyncMock()
    provider.create_nodes = AsyncMock(return_value=1)
    provider.create_relationships = AsyncMock(return_value=1)
    return provider


class TestEntity:
    """Tests for Entity model."""

    def test_entity_creation(self) -> None:
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

    def test_entity_default_confidence(self) -> None:
        """Test entity default confidence value."""
        entity = Entity(
            id="org_acme",
            type=EntityType.ORGANIZATION,
            properties={"name": "Acme Corp"},
        )
        assert entity.confidence == 1.0

    def test_entity_types(self) -> None:
        """Test all entity types."""
        assert EntityType.PERSON.value == "Person"
        assert EntityType.ORGANIZATION.value == "Organization"
        assert EntityType.DOCUMENT_RULE.value == "DocumentRule"
        assert EntityType.DOCUMENT.value == "Document"
        assert EntityType.CHUNK.value == "Chunk"


class TestRelationship:
    """Tests for Relationship model."""

    def test_relationship_creation(self) -> None:
        """Test basic relationship creation."""
        rel = FeaturesRelationship(
            from_id="person_john",
            to_id="org_acme",
            type="WORKS_AT",
            properties={"since": "2020"},
        )
        assert rel.from_id == "person_john"
        assert rel.to_id == "org_acme"
        assert rel.type == "WORKS_AT"


class TestEntityModels:
    """Tests for entity Pydantic models."""

    def test_person_creation(self) -> None:
        """Test creating a Person entity."""
        person = Person(
            name="John Doe",
            confidence=0.95,
            role="CEO",
            organization="Acme Corp",
        )

        assert person.name == "John Doe"
        assert person.confidence == 0.95
        assert person.role == "CEO"
        assert person.organization == "Acme Corp"

    def test_person_to_node_dict(self) -> None:
        """Test Person conversion to Neo4j node properties."""
        person = Person(
            name="Jane Smith",
            confidence=0.85,
            role="CTO",
        )

        node = person.to_node_dict()

        assert node["name"] == "Jane Smith"
        assert node["role"] == "CTO"
        assert node["confidence"] == 0.85

    def test_organization_creation(self) -> None:
        """Test creating an Organization entity."""
        org = Organization(
            name="OpenAI",
            confidence=0.9,
            org_type="company",
            location="San Francisco",
        )

        assert org.name == "OpenAI"
        assert org.org_type == "company"
        assert org.location == "San Francisco"

    def test_organization_to_node_dict(self) -> None:
        """Test Organization conversion to Neo4j node properties."""
        org = Organization(
            name="Google",
            confidence=0.95,
            org_type="company",
        )

        node = org.to_node_dict()

        assert node["name"] == "Google"
        assert node["type"] == "company"
        assert node["confidence"] == 0.95

    def test_date_entity_creation(self) -> None:
        """Test creating a DateEntity."""
        date = DateEntity(
            name="January 15, 2024",
            confidence=0.8,
            date_type="event",
            normalized="2024-01-15",
        )

        assert date.name == "January 15, 2024"
        assert date.normalized == "2024-01-15"
        assert date.date_type == "event"

    def test_document_rule_creation(self) -> None:
        """Test creating a DocumentRule entity."""
        rule = DocumentRule(
            name="All documents must be reviewed within 5 days",
            confidence=0.75,
            priority="high",
            category="compliance",
        )

        assert rule.priority == "high"
        assert rule.category == "compliance"

    def test_relationship_creation(self) -> None:
        """Test creating a Relationship."""
        rel = Relationship(
            from_entity="John Doe",
            to_entity="Acme Corp",
            rel_type="WORKS_AT",
            properties={"since": "2020"},
        )

        assert rel.from_entity == "John Doe"
        assert rel.to_entity == "Acme Corp"
        assert rel.rel_type == "WORKS_AT"
        assert rel.properties["since"] == "2020"


class TestExtractionResult:
    """Tests for ExtractionResult model (from features)."""

    def test_extraction_result_default(self) -> None:
        """Test default extraction result."""
        result = FeaturesExtractionResult()
        assert result.entities == []
        assert result.relationships == []
        assert result.document_id is None
        assert result.chunk_count == 0

    def test_extraction_result_with_data(self) -> None:
        """Test extraction result with data."""
        entity = Entity(id="test", type=EntityType.PERSON, properties={})
        rel = FeaturesRelationship(from_id="a", to_id="b", type="REL")
        result = FeaturesExtractionResult(
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

    def test_schema_parsing(self) -> None:
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

    def test_schema_empty(self) -> None:
        """Test schema with empty data."""
        schema = ExtractedEntitiesSchema()
        assert schema.persons == []
        assert schema.organizations == []
        assert schema.rules == []
        assert schema.relationships == []

    def test_schema_null_values(self) -> None:
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

    def test_total_entities(self) -> None:
        """Test total_entities property."""
        result = ExtractionResult(
            persons=[
                Person(name="A", confidence=0.9),
                Person(name="B", confidence=0.8),
            ],
            organizations=[Organization(name="C", confidence=0.85)],
            dates=[],
            document_rules=[DocumentRule(name="D", confidence=0.7)],
        )

        assert result.total_entities == 4

    def test_filter_by_confidence(self) -> None:
        """Test filtering entities by confidence threshold."""
        result = ExtractionResult(
            persons=[
                Person(name="High", confidence=0.9),
                Person(name="Low", confidence=0.5),
            ],
            organizations=[
                Organization(name="HighOrg", confidence=0.85),
                Organization(name="LowOrg", confidence=0.6),
            ],
        )

        filtered = result.filter_by_confidence(0.8)

        assert len(filtered.persons) == 1
        assert filtered.persons[0].name == "High"
        assert len(filtered.organizations) == 1
        assert filtered.organizations[0].name == "HighOrg"

    def test_empty_result(self) -> None:
        """Test empty ExtractionResult."""
        result = ExtractionResult()

        assert result.total_entities == 0
        assert len(result.persons) == 0
        assert len(result.organizations) == 0


class TestData2NeoExtractor:
    """Tests for Data2NeoExtractor class (from features)."""

    def test_extractor_initialization(self, mock_config: Any) -> None:
        """Test extractor initialization."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        assert extractor.confidence_threshold == 0.7
        assert extractor.batch_size == 100

    def test_chunk_text_short(self, mock_config: Any) -> None:
        """Test chunking short text."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        text = "Short text"
        chunks = extractor._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long(self, mock_config: Any) -> None:
        """Test chunking long text."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        text = "Paragraph one.\n\n" * 100  # Long text
        chunks = extractor._chunk_text(text, chunk_size=100)
        assert len(chunks) > 1

    def test_generate_entity_id(self, mock_config: Any) -> None:
        """Test entity ID generation."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        entity_id = extractor._generate_entity_id("person", "John Doe")
        assert entity_id == "person_john_doe"

    def test_generate_entity_id_special_chars(self, mock_config: Any) -> None:
        """Test entity ID generation with special characters."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        entity_id = extractor._generate_entity_id("organization", "Acme, Inc.")
        assert "_" in entity_id
        assert "," not in entity_id

    def test_parse_extraction_response_valid(self, mock_config: Any) -> None:
        """Test parsing valid JSON response."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
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

    def test_parse_extraction_response_invalid(self, mock_config: Any) -> None:
        """Test parsing invalid response."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
        response = "This is not JSON"
        result = extractor._parse_extraction_response(response)
        assert len(result.persons) == 0

    def test_convert_to_entities(self, mock_config: Any) -> None:
        """Test converting schema to entities."""
        extractor = FeaturesData2NeoExtractor(config=mock_config)
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

    def test_convert_to_entities_confidence_filter(self, mock_config: Any) -> None:
        """Test confidence threshold filtering."""
        mock_config.data2neo_confidence = 0.8
        extractor = FeaturesData2NeoExtractor(config=mock_config)
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
    async def test_extract_entities_no_provider(self, mock_config: Any) -> None:
        """Test extraction without LLM provider."""
        extractor = FeaturesData2NeoExtractor(config=mock_config, llm_provider=None)
        result = await extractor.extract_entities("Test text", "doc_1")
        assert len(result.entities) == 0
        assert result.document_id == "doc_1"

    @pytest.mark.asyncio
    async def test_extract_entities_with_provider(
        self, mock_config: Any, mock_llm_provider: Any
    ) -> None:
        """Test extraction with LLM provider."""
        mock_llm_provider.generate_content_async.return_value = MagicMock(
            content='{"persons": [{"id": "p1", "name": "John"}], "organizations": [], "rules": [], "relationships": []}'
        )
        extractor = FeaturesData2NeoExtractor(
            config=mock_config, llm_provider=mock_llm_provider
        )
        await extractor.extract_entities("John works at Acme", "doc_1")
        assert mock_llm_provider.generate_content_async.called
        # Result depends on parsing

    @pytest.mark.asyncio
    async def test_import_to_graph_no_provider(self, mock_config: Any) -> None:
        """Test import without graph provider."""
        extractor = FeaturesData2NeoExtractor(config=mock_config, graph_provider=None)
        result = FeaturesExtractionResult(
            entities=[
                Entity(id="p1", type=EntityType.PERSON, properties={"name": "John"})
            ],
        )
        counts = await extractor.import_to_graph(result)
        assert counts["nodes"] == 0
        assert counts["relationships"] == 0

    @pytest.mark.asyncio
    async def test_import_to_graph_with_provider(
        self, mock_config: Any, mock_graph_provider: Any
    ) -> None:
        """Test import with graph provider."""
        extractor = FeaturesData2NeoExtractor(
            config=mock_config, graph_provider=mock_graph_provider
        )
        result = FeaturesExtractionResult(
            entities=[
                Entity(id="p1", type=EntityType.PERSON, properties={"name": "John"}),
                Entity(
                    id="o1", type=EntityType.ORGANIZATION, properties={"name": "Acme"}
                ),
            ],
            relationships=[
                FeaturesRelationship(from_id="p1", to_id="o1", type="WORKS_AT"),
            ],
        )
        counts = await extractor.import_to_graph(result)
        assert mock_graph_provider.create_nodes.called
        assert counts["nodes"] > 0

    @pytest.mark.asyncio
    async def test_extract_and_import(
        self, mock_config: Any, mock_llm_provider: Any, mock_graph_provider: Any
    ) -> None:
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
        extractor = FeaturesData2NeoExtractor(
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
    async def test_create_extractor_disabled(self, mock_config: Any) -> None:
        """Test factory with data2neo disabled."""
        mock_config.enable_data2neo = False
        extractor = await create_data2neo_extractor(mock_config)
        assert extractor.llm_provider is None
        assert extractor.graph_provider is None

    @pytest.mark.asyncio
    async def test_create_extractor_with_providers(
        self, mock_config: Any, mock_llm_provider: Any, mock_graph_provider: Any
    ) -> None:
        """Test factory with provided providers."""
        extractor = await create_data2neo_extractor(
            mock_config,
            llm_provider=mock_llm_provider,
            graph_provider=mock_graph_provider,
        )
        assert extractor.llm_provider == mock_llm_provider
        assert extractor.graph_provider == mock_graph_provider

    @pytest.fixture
    def mock_templates(self) -> Any:
        """Create mock Jinja2 templates."""
        return DictLoader(
            {
                "system/entity_extraction.j2": "Extract entities: {{ response_schema }}",
                "user/entity_extraction.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def mock_agent(self) -> Any:
        """Create mock GeminiAgent."""
        agent = MagicMock()
        agent._create_generative_model = MagicMock(return_value=MagicMock())
        agent._call_api_with_retry = AsyncMock()
        return agent

    @pytest.fixture
    def mock_config(self, tmp_path: Path) -> Any:
        """Create mock AppConfig."""
        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100
        return config

    @pytest.fixture
    def extractor(self, mock_config: Any, mock_agent: Any, mock_templates: Any) -> Any:
        """Create Data2NeoExtractor with mocks."""
        jinja_env = Environment(loader=mock_templates)
        return Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            jinja_env=jinja_env,
        )

    @pytest.mark.asyncio
    async def test_extract_entities_success(
        self, extractor: Any, mock_agent: Any
    ) -> None:
        """Test successful entity extraction."""
        mock_response = json.dumps(
            {
                "persons": [{"name": "John Doe", "confidence": 0.9, "role": "CEO"}],
                "organizations": [
                    {"name": "Acme Corp", "confidence": 0.85, "org_type": "company"}
                ],
                "dates": [],
                "document_rules": [],
                "relationships": [
                    {
                        "from_entity": "John Doe",
                        "to_entity": "Acme Corp",
                        "rel_type": "WORKS_AT",
                    }
                ],
            }
        )
        mock_agent._call_api_with_retry.return_value = mock_response

        result = await extractor.extract_entities(
            "Sample OCR text with John Doe, CEO of Acme Corp"
        )

        assert len(result.persons) == 1
        assert result.persons[0].name == "John Doe"
        assert len(result.organizations) == 1
        assert result.organizations[0].name == "Acme Corp"
        assert len(result.relationships) == 1

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self, extractor: Any) -> None:
        """Test extraction with empty text raises error."""
        with pytest.raises(ValueError, match="OCR text cannot be empty"):
            await extractor.extract_entities("")

    @pytest.mark.asyncio
    async def test_extract_entities_whitespace_only(self, extractor: Any) -> None:
        """Test extraction with whitespace-only text raises error."""
        with pytest.raises(ValueError, match="OCR text cannot be empty"):
            await extractor.extract_entities("   \n\t  ")

    @pytest.mark.asyncio
    async def test_extract_entities_confidence_filter(
        self, extractor: Any, mock_agent: Any
    ) -> None:
        """Test that confidence threshold filtering works."""
        mock_response = json.dumps(
            {
                "persons": [
                    {"name": "High Conf", "confidence": 0.9},
                    {"name": "Low Conf", "confidence": 0.5},
                ],
                "organizations": [],
                "dates": [],
                "document_rules": [],
                "relationships": [],
            }
        )
        mock_agent._call_api_with_retry.return_value = mock_response

        result = await extractor.extract_entities("Some text")

        # Only the high confidence person should remain (threshold is 0.7)
        assert len(result.persons) == 1
        assert result.persons[0].name == "High Conf"

    @pytest.mark.asyncio
    async def test_extract_entities_with_markdown_wrapper(
        self, extractor: Any, mock_agent: Any
    ) -> None:
        """Test extraction handles markdown code blocks."""
        mock_response = """```json
{
    "persons": [{"name": "Test Person", "confidence": 0.8}],
    "organizations": [],
    "dates": [],
    "document_rules": [],
    "relationships": []
}
```"""
        mock_agent._call_api_with_retry.return_value = mock_response

        result = await extractor.extract_entities("OCR text")

        assert len(result.persons) == 1
        assert result.persons[0].name == "Test Person"

    @pytest.mark.asyncio
    async def test_extract_entities_empty_response(
        self, extractor: Any, mock_agent: Any
    ) -> None:
        """Test extraction handles empty response."""
        mock_agent._call_api_with_retry.return_value = ""

        result = await extractor.extract_entities("Some text")

        assert result.total_entities == 0

    @pytest.mark.asyncio
    async def test_extract_entities_partial_invalid_data(
        self, extractor: Any, mock_agent: Any
    ) -> None:
        """Test extraction recovers from partially invalid data."""
        # Missing required 'confidence' field in one person
        mock_response = json.dumps(
            {
                "persons": [
                    {"name": "Valid", "confidence": 0.8},
                    {"name": "Invalid"},  # Missing confidence
                ],
                "organizations": [],
                "dates": [],
                "document_rules": [],
                "relationships": [],
            }
        )
        mock_agent._call_api_with_retry.return_value = mock_response

        result = await extractor.extract_entities("Some text")

        # Only the valid person should be extracted
        assert len(result.persons) == 1
        assert result.persons[0].name == "Valid"

    def test_generate_entity_id(self) -> None:
        """Test entity ID generation."""
        id1 = Data2NeoExtractor._generate_entity_id("person", "John Doe")
        id2 = Data2NeoExtractor._generate_entity_id("person", "John Doe")
        id3 = Data2NeoExtractor._generate_entity_id("person", "Jane Smith")

        assert id1 == id2  # Same name should produce same ID
        assert id1 != id3  # Different names should produce different IDs
        assert id1.startswith("person_")

    def test_generate_entity_id_normalization(self) -> None:
        """Test entity ID generation normalizes names."""
        id1 = Data2NeoExtractor._generate_entity_id("org", "  Acme Corp  ")
        id2 = Data2NeoExtractor._generate_entity_id("org", "acme corp")

        assert id1 == id2  # Should normalize to same ID

    def test_infer_relationship_labels(self) -> None:
        """Test relationship label inference."""
        from_label, to_label = Data2NeoExtractor._infer_relationship_labels("WORKS_AT")
        assert from_label == "Person"
        assert to_label == "Organization"

        from_label, to_label = Data2NeoExtractor._infer_relationship_labels(
            "UNKNOWN_TYPE"
        )
        assert from_label == "Entity"
        assert to_label == "Entity"

    def test_get_statistics(self, extractor: Any) -> None:
        """Test statistics tracking."""
        stats = extractor.get_statistics()

        assert stats["extraction_count"] == 0
        assert stats["total_entities"] == 0


class TestData2NeoExtractorGraphWriting:
    """Tests for Data2NeoExtractor graph writing functionality."""

    @pytest.fixture
    def mock_graph_provider(self) -> Any:
        """Create mock GraphProvider."""
        provider = AsyncMock()
        provider.create_nodes = AsyncMock(return_value=1)
        provider.create_relationships = AsyncMock(return_value=1)
        return provider

    @pytest.fixture
    def mock_templates(self) -> Any:
        """Create mock Jinja2 templates."""
        return DictLoader(
            {
                "system/entity_extraction.j2": "Extract entities: {{ response_schema }}",
                "user/entity_extraction.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def extractor_with_graph(
        self, mock_graph_provider: Any, mock_templates: Any, tmp_path: Path
    ) -> Any:
        """Create extractor with graph provider."""
        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100

        agent = MagicMock()
        jinja_env = Environment(loader=mock_templates)

        return Data2NeoExtractor(
            config=config,
            agent=agent,
            graph_provider=mock_graph_provider,
            jinja_env=jinja_env,
        )

    @pytest.mark.asyncio
    async def test_write_to_graph_no_provider(
        self, mock_templates: Any, tmp_path: Path
    ) -> None:
        """Test write_to_graph raises error without provider."""
        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100

        agent = MagicMock()
        jinja_env = Environment(loader=mock_templates)

        extractor = Data2NeoExtractor(
            config=config,
            agent=agent,
            jinja_env=jinja_env,
        )

        result = ExtractionResult(persons=[Person(name="Test", confidence=0.9)])

        with pytest.raises(RuntimeError, match="GraphProvider not configured"):
            await extractor.write_to_graph(result)

    @pytest.mark.asyncio
    async def test_write_to_graph_success(
        self, extractor_with_graph: Any, mock_graph_provider: Any
    ) -> None:
        """Test successful graph writing."""
        result = ExtractionResult(
            persons=[Person(name="John", confidence=0.9, role="CEO")],
            organizations=[
                Organization(name="Acme", confidence=0.85, org_type="company")
            ],
            relationships=[
                Relationship(
                    from_entity="John",
                    to_entity="Acme",
                    rel_type="WORKS_AT",
                )
            ],
        )

        counts = await extractor_with_graph.write_to_graph(result)

        assert counts["persons"] == 1
        assert counts["organizations"] == 1
        assert counts["relationships"] == 1
        mock_graph_provider.create_nodes.assert_called()

    @pytest.mark.asyncio
    async def test_write_to_graph_empty_result(
        self, extractor_with_graph: Any, mock_graph_provider: Any
    ) -> None:
        """Test writing empty result."""
        result = ExtractionResult()

        counts = await extractor_with_graph.write_to_graph(result)

        assert counts["persons"] == 0
        assert counts["organizations"] == 0
        mock_graph_provider.create_nodes.assert_not_called()
