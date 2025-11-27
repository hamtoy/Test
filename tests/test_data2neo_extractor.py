"""Tests for the Data2NeoExtractor module.

Tests cover:
- Entity model creation and validation
- Entity extraction from OCR text
- Confidence threshold filtering
- Graph writing (mocked)
- Error handling
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from jinja2 import Environment, DictLoader

from src.config import AppConfig
from src.graph.data2neo_extractor import Data2NeoExtractor
from src.graph.entities import (
    DateEntity,
    DocumentRule,
    ExtractionResult,
    Organization,
    Person,
    Relationship,
)


class TestEntityModels:
    """Tests for entity Pydantic models."""

    def test_person_creation(self):
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

    def test_person_to_node_dict(self):
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

    def test_organization_creation(self):
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

    def test_organization_to_node_dict(self):
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

    def test_date_entity_creation(self):
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

    def test_document_rule_creation(self):
        """Test creating a DocumentRule entity."""
        rule = DocumentRule(
            name="All documents must be reviewed within 5 days",
            confidence=0.75,
            priority="high",
            category="compliance",
        )

        assert rule.priority == "high"
        assert rule.category == "compliance"

    def test_relationship_creation(self):
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
    """Tests for ExtractionResult model."""

    def test_total_entities(self):
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

    def test_filter_by_confidence(self):
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

    def test_empty_result(self):
        """Test empty ExtractionResult."""
        result = ExtractionResult()

        assert result.total_entities == 0
        assert len(result.persons) == 0
        assert len(result.organizations) == 0


class TestData2NeoExtractor:
    """Tests for Data2NeoExtractor class."""

    @pytest.fixture
    def mock_templates(self):
        """Create mock Jinja2 templates."""
        return DictLoader(
            {
                "prompt_entity_extraction.j2": "Extract entities: {{ response_schema }}",
                "entity_extraction_user.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def mock_agent(self):
        """Create mock GeminiAgent."""
        agent = MagicMock()
        agent._create_generative_model = MagicMock(return_value=MagicMock())
        agent._call_api_with_retry = AsyncMock()
        return agent

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock AppConfig."""
        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100
        return config

    @pytest.fixture
    def extractor(self, mock_config, mock_agent, mock_templates):
        """Create Data2NeoExtractor with mocks."""
        jinja_env = Environment(loader=mock_templates)
        return Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            jinja_env=jinja_env,
        )

    @pytest.mark.asyncio
    async def test_extract_entities_success(self, extractor, mock_agent):
        """Test successful entity extraction."""
        mock_response = json.dumps(
            {
                "persons": [
                    {"name": "John Doe", "confidence": 0.9, "role": "CEO"}
                ],
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

        result = await extractor.extract_entities("Sample OCR text with John Doe, CEO of Acme Corp")

        assert len(result.persons) == 1
        assert result.persons[0].name == "John Doe"
        assert len(result.organizations) == 1
        assert result.organizations[0].name == "Acme Corp"
        assert len(result.relationships) == 1

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self, extractor):
        """Test extraction with empty text raises error."""
        with pytest.raises(ValueError, match="OCR text cannot be empty"):
            await extractor.extract_entities("")

    @pytest.mark.asyncio
    async def test_extract_entities_whitespace_only(self, extractor):
        """Test extraction with whitespace-only text raises error."""
        with pytest.raises(ValueError, match="OCR text cannot be empty"):
            await extractor.extract_entities("   \n\t  ")

    @pytest.mark.asyncio
    async def test_extract_entities_confidence_filter(self, extractor, mock_agent):
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
    async def test_extract_entities_with_markdown_wrapper(self, extractor, mock_agent):
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
    async def test_extract_entities_empty_response(self, extractor, mock_agent):
        """Test extraction handles empty response."""
        mock_agent._call_api_with_retry.return_value = ""

        result = await extractor.extract_entities("Some text")

        assert result.total_entities == 0

    @pytest.mark.asyncio
    async def test_extract_entities_partial_invalid_data(self, extractor, mock_agent):
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

    def test_generate_entity_id(self):
        """Test entity ID generation."""
        id1 = Data2NeoExtractor._generate_entity_id("person", "John Doe")
        id2 = Data2NeoExtractor._generate_entity_id("person", "John Doe")
        id3 = Data2NeoExtractor._generate_entity_id("person", "Jane Smith")

        assert id1 == id2  # Same name should produce same ID
        assert id1 != id3  # Different names should produce different IDs
        assert id1.startswith("person_")

    def test_generate_entity_id_normalization(self):
        """Test entity ID generation normalizes names."""
        id1 = Data2NeoExtractor._generate_entity_id("org", "  Acme Corp  ")
        id2 = Data2NeoExtractor._generate_entity_id("org", "acme corp")

        assert id1 == id2  # Should normalize to same ID

    def test_infer_relationship_labels(self):
        """Test relationship label inference."""
        from_label, to_label = Data2NeoExtractor._infer_relationship_labels(
            "WORKS_AT"
        )
        assert from_label == "Person"
        assert to_label == "Organization"

        from_label, to_label = Data2NeoExtractor._infer_relationship_labels(
            "UNKNOWN_TYPE"
        )
        assert from_label == "Entity"
        assert to_label == "Entity"

    def test_get_statistics(self, extractor):
        """Test statistics tracking."""
        stats = extractor.get_statistics()

        assert stats["extraction_count"] == 0
        assert stats["total_entities"] == 0


class TestData2NeoExtractorGraphWriting:
    """Tests for Data2NeoExtractor graph writing functionality."""

    @pytest.fixture
    def mock_graph_provider(self):
        """Create mock GraphProvider."""
        provider = AsyncMock()
        provider.create_nodes = AsyncMock(return_value=1)
        provider.create_relationships = AsyncMock(return_value=1)
        return provider

    @pytest.fixture
    def mock_templates(self):
        """Create mock Jinja2 templates."""
        return DictLoader(
            {
                "prompt_entity_extraction.j2": "Extract entities: {{ response_schema }}",
                "entity_extraction_user.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def extractor_with_graph(self, mock_graph_provider, mock_templates, tmp_path):
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
    async def test_write_to_graph_no_provider(self, mock_templates, tmp_path):
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

        result = ExtractionResult(
            persons=[Person(name="Test", confidence=0.9)]
        )

        with pytest.raises(RuntimeError, match="GraphProvider not configured"):
            await extractor.write_to_graph(result)

    @pytest.mark.asyncio
    async def test_write_to_graph_success(
        self, extractor_with_graph, mock_graph_provider
    ):
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
        self, extractor_with_graph, mock_graph_provider
    ):
        """Test writing empty result."""
        result = ExtractionResult()

        counts = await extractor_with_graph.write_to_graph(result)

        assert counts["persons"] == 0
        assert counts["organizations"] == 0
        mock_graph_provider.create_nodes.assert_not_called()
