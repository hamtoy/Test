"""Data2Neo Extractor for OCR text to Neo4j Knowledge Graph.

This module provides entity extraction from OCR text and imports
extracted entities into Neo4j graph database.

Phase 3: Integration with worker.py for automated pipeline processing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator

from src.config.constants import DEFAULT_MAX_OUTPUT_TOKENS

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.core.interfaces import GraphProvider, LLMProvider

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Supported entity types for extraction."""

    PERSON = "Person"
    ORGANIZATION = "Organization"
    DOCUMENT_RULE = "DocumentRule"
    DOCUMENT = "Document"
    CHUNK = "Chunk"


class Entity(BaseModel):
    """Extracted entity with properties."""

    id: str = Field(..., description="Unique identifier")
    type: EntityType = Field(..., description="Entity type")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Entity properties",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score",
    )


class Relationship(BaseModel):
    """Relationship between entities."""

    from_id: str = Field(..., description="Source entity ID")
    to_id: str = Field(..., description="Target entity ID")
    type: str = Field(..., description="Relationship type")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Relationship properties",
    )


class ExtractionResult(BaseModel):
    """Result from entity extraction."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    document_id: str | None = None
    chunk_count: int = 0


class ExtractedEntitiesSchema(BaseModel):
    """Schema for LLM extraction response."""

    persons: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted persons",
    )
    organizations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted organizations",
    )
    rules: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted document rules",
    )
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted relationships",
    )

    @field_validator(
        "persons",
        "organizations",
        "rules",
        "relationships",
        mode="before",
    )
    @classmethod
    def ensure_list(cls, v: Any) -> list[Any]:
        """Ensure the value is a list.

        Args:
            v: The value to convert to a list.

        Returns:
            The value as a list.
        """
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]


@dataclass
class Data2NeoExtractor:
    """Extracts entities from OCR text and writes to Neo4j.

    This extractor uses an LLM to identify entities (Person, Organization,
    DocumentRule) from OCR text and stores them in a Neo4j knowledge graph.

    Attributes:
        config: Application configuration
        llm_provider: LLM provider for entity extraction
        graph_provider: Graph database provider for storage
        confidence_threshold: Minimum confidence for entity inclusion
        batch_size: Batch size for graph writes

    Example:
        >>> extractor = Data2NeoExtractor(config, llm, graph)
        >>> result = await extractor.extract_and_import(ocr_text, document_path)
        >>> print(f"Imported {len(result.entities)} entities")
    """

    config: AppConfig
    llm_provider: LLMProvider | None = None
    graph_provider: GraphProvider | None = None
    confidence_threshold: float = 0.7
    batch_size: int = 100
    extraction_temperature: float = 0.1
    _extraction_prompt: str = field(init=False, default="")

    def __post_init__(self) -> None:
        """Initialize extractor with config values."""
        if hasattr(self.config, "data2neo_confidence"):
            self.confidence_threshold = self.config.data2neo_confidence
        if hasattr(self.config, "data2neo_batch_size"):
            self.batch_size = self.config.data2neo_batch_size
        if hasattr(self.config, "data2neo_temperature"):
            self.extraction_temperature = self.config.data2neo_temperature

        self._extraction_prompt = self._build_extraction_prompt()

    def _build_extraction_prompt(self) -> str:
        """Build the entity extraction prompt."""
        return """You are an entity extraction system. Extract entities and relationships from the given OCR text.

For each entity, provide:
- id: A unique identifier (use name or generate a unique id)
- name: The entity name
- type: One of "Person", "Organization", or "DocumentRule"
- Additional properties relevant to the entity type

For Person entities, extract:
- name: Full name
- role: Job title or role if mentioned

For Organization entities, extract:
- name: Organization name
- type: Organization type (company, government, non-profit, etc.)

For DocumentRule entities, extract:
- text: The rule text
- priority: Priority level (high, medium, low) if mentioned

For relationships, provide:
- from_id: Source entity ID
- to_id: Target entity ID
- type: Relationship type (WORKS_AT, AFFILIATED_WITH, REFERENCES, etc.)

Respond ONLY with a valid JSON object in this exact format:
{
    "persons": [{"id": "...", "name": "...", "role": "..."}],
    "organizations": [{"id": "...", "name": "...", "type": "..."}],
    "rules": [{"id": "...", "text": "...", "priority": "..."}],
    "relationships": [{"from_id": "...", "to_id": "...", "type": "..."}]
}

OCR Text to analyze:
"""

    def _chunk_text(self, text: str, chunk_size: int = 4000) -> list[str]:
        """Split text into chunks for processing.

        Args:
            text: Input text to chunk
            chunk_size: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        # Split on paragraph boundaries when possible
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(para) > chunk_size:
                    # Split long paragraph into smaller pieces
                    chunks.extend(
                        para[i : i + chunk_size]
                        for i in range(0, len(para), chunk_size)
                    )
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    def _generate_entity_id(self, entity_type: str, name: str) -> str:
        """Generate a unique entity ID.

        Args:
            entity_type: Type of entity
            name: Entity name

        Returns:
            Unique identifier string
        """
        # Normalize name for ID
        normalized = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        return f"{entity_type.lower()}_{normalized}"

    def _parse_extraction_response(self, response_text: str) -> ExtractedEntitiesSchema:
        """Parse LLM response into structured entities.

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed extraction schema
        """
        # Try to extract JSON from the response
        try:
            # First, try to parse the entire response as JSON
            data = json.loads(response_text.strip())
            return ExtractedEntitiesSchema.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            # Look for JSON in the response - find balanced braces
            start_idx = response_text.find("{")
            if start_idx == -1:
                return ExtractedEntitiesSchema()

            # Find matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i, char in enumerate(response_text[start_idx:], start_idx):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

            if brace_count == 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                data = json.loads(json_str)
                return ExtractedEntitiesSchema.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse extraction response: %s", e)

        # Return empty result if parsing fails
        return ExtractedEntitiesSchema()

    def _convert_to_entities(
        self,
        schema: ExtractedEntitiesSchema,
        document_id: str,
    ) -> ExtractionResult:
        """Convert parsed schema to Entity objects.

        Args:
            schema: Parsed extraction schema
            document_id: Parent document ID

        Returns:
            ExtractionResult with entities and relationships
        """
        entities: list[Entity] = []
        relationships: list[Relationship] = []

        # Process persons
        for person in schema.persons:
            name = person.get("name", "")
            if not name:
                continue
            entity_id = person.get("id") or self._generate_entity_id("person", name)
            entities.append(
                Entity(
                    id=entity_id,
                    type=EntityType.PERSON,
                    properties={"name": name, "role": person.get("role", "")},
                    confidence=float(person.get("confidence", 0.8)),
                ),
            )

        # Process organizations
        for org in schema.organizations:
            name = org.get("name", "")
            if not name:
                continue
            entity_id = org.get("id") or self._generate_entity_id("organization", name)
            entities.append(
                Entity(
                    id=entity_id,
                    type=EntityType.ORGANIZATION,
                    properties={"name": name, "type": org.get("type", "")},
                    confidence=float(org.get("confidence", 0.8)),
                ),
            )

        # Process rules
        for rule in schema.rules:
            text = rule.get("text", "")
            if not text:
                continue
            entity_id = rule.get("id") or self._generate_entity_id("rule", text[:30])
            entities.append(
                Entity(
                    id=entity_id,
                    type=EntityType.DOCUMENT_RULE,
                    properties={
                        "text": text,
                        "priority": rule.get("priority", "medium"),
                    },
                    confidence=float(rule.get("confidence", 0.7)),
                ),
            )

        # Process relationships
        for rel in schema.relationships:
            from_id = rel.get("from_id", "")
            to_id = rel.get("to_id", "")
            rel_type = rel.get("type", "RELATED_TO")
            if from_id and to_id:
                relationships.append(
                    Relationship(
                        from_id=from_id,
                        to_id=to_id,
                        type=rel_type,
                        properties=rel.get("properties", {}),
                    ),
                )

        # Filter by confidence threshold
        entities = [e for e in entities if e.confidence >= self.confidence_threshold]

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            document_id=document_id,
            chunk_count=0,
        )

    async def extract_entities(
        self,
        ocr_text: str,
        document_id: str,
    ) -> ExtractionResult:
        """Extract entities from OCR text using LLM.

        Args:
            ocr_text: OCR text to analyze
            document_id: Unique document identifier

        Returns:
            ExtractionResult containing entities and relationships
        """
        if not self.llm_provider:
            logger.warning("No LLM provider available, returning empty result")
            return ExtractionResult(document_id=document_id)

        # Chunk text if too long
        chunks = self._chunk_text(ocr_text)
        all_entities: list[Entity] = []
        all_relationships: list[Relationship] = []

        for i, chunk in enumerate(chunks):
            prompt = self._extraction_prompt + chunk

            try:
                result = await self.llm_provider.generate_content_async(
                    prompt=prompt,
                    temperature=self.extraction_temperature,
                    max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                )
                schema = self._parse_extraction_response(result.content)
                chunk_result = self._convert_to_entities(schema, document_id)

                all_entities.extend(chunk_result.entities)
                all_relationships.extend(chunk_result.relationships)

            except Exception as e:  # noqa: BLE001
                logger.error("Entity extraction failed for chunk %d: %s", i, e)
                continue

        # Deduplicate entities by ID
        seen_ids = set()
        unique_entities = []
        for entity in all_entities:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                unique_entities.append(entity)

        return ExtractionResult(
            entities=unique_entities,
            relationships=all_relationships,
            document_id=document_id,
            chunk_count=len(chunks),
        )

    async def import_to_graph(self, result: ExtractionResult) -> dict[str, int]:
        """Import extraction result to Neo4j graph.

        Args:
            result: Extraction result to import

        Returns:
            Dictionary with counts of created nodes/relationships
        """
        if not self.graph_provider:
            logger.warning("No graph provider available, skipping import")
            return {"nodes": 0, "relationships": 0}

        counts = {"nodes": 0, "relationships": 0}

        # Group entities by type
        entities_by_type: dict[EntityType, list[dict[str, Any]]] = {}
        for entity in result.entities:
            if entity.type not in entities_by_type:
                entities_by_type[entity.type] = []
            node_props = {"id": entity.id, **entity.properties}
            entities_by_type[entity.type].append(node_props)

        # Create nodes by type with batching
        for entity_type, nodes in entities_by_type.items():
            label = entity_type.value
            for i in range(0, len(nodes), self.batch_size):
                batch = nodes[i : i + self.batch_size]
                try:
                    count = await self.graph_provider.create_nodes(
                        nodes=batch,
                        label=label,
                        merge_on="id",
                    )
                    counts["nodes"] += count
                except Exception as e:  # noqa: BLE001
                    logger.error("Failed to create %s nodes: %s", label, e)

        # Create relationships with batching
        if result.relationships:
            # Build entity ID to label mapping
            entity_labels = {e.id: e.type.value for e in result.entities}

            # Group relationships by type
            rels_by_type: dict[str, list[dict[str, Any]]] = {}
            for rel in result.relationships:
                if rel.type not in rels_by_type:
                    rels_by_type[rel.type] = []
                rel_props = {
                    "from_id": rel.from_id,
                    "to_id": rel.to_id,
                    **rel.properties,
                }
                rels_by_type[rel.type].append(rel_props)

            for rel_type, rels in rels_by_type.items():
                for i in range(0, len(rels), self.batch_size):
                    batch = rels[i : i + self.batch_size]
                    try:
                        # Determine labels from entity mapping, fallback to defaults
                        first_rel = batch[0] if batch else {}
                        from_label = entity_labels.get(
                            first_rel.get("from_id", ""),
                            "Person",
                        )
                        to_label = entity_labels.get(
                            first_rel.get("to_id", ""),
                            "Organization",
                        )

                        count = await self.graph_provider.create_relationships(
                            rels=batch,
                            rel_type=rel_type,
                            from_label=from_label,
                            to_label=to_label,
                            from_key="id",
                            to_key="id",
                        )
                        counts["relationships"] += count
                    except Exception as e:  # noqa: BLE001
                        logger.error(
                            "Failed to create %s relationships: %s",
                            rel_type,
                            e,
                        )

        logger.info(
            "Imported %d nodes and %d relationships",
            counts["nodes"],
            counts["relationships"],
        )
        return counts

    async def extract_and_import(
        self,
        ocr_text: str,
        document_path: str,
    ) -> ExtractionResult:
        """Extract entities from OCR text and import to graph.

        This is the main entry point for the Data2Neo pipeline.

        Args:
            ocr_text: OCR text content
            document_path: Path or identifier for the source document

        Returns:
            ExtractionResult with imported entities
        """
        document_id = self._generate_entity_id("document", document_path)

        # Create document node first
        if self.graph_provider:
            try:
                await self.graph_provider.create_nodes(
                    nodes=[{"id": document_id, "path": document_path}],
                    label="Document",
                    merge_on="id",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to create document node: %s", e)

        # Extract entities
        result = await self.extract_entities(ocr_text, document_id)

        # Import to graph
        await self.import_to_graph(result)

        return result


def create_data2neo_extractor(
    config: AppConfig,
    llm_provider: LLMProvider | None = None,
    graph_provider: GraphProvider | None = None,
) -> Data2NeoExtractor:
    """Factory function to create Data2NeoExtractor.

    Args:
        config: Application configuration
        llm_provider: Optional LLM provider (will be created if not provided)
        graph_provider: Optional graph provider (will be created if not provided)

    Returns:
        Configured Data2NeoExtractor instance
    """
    # Get providers if not provided and data2neo is enabled
    if getattr(config, "enable_data2neo", False):
        if llm_provider is None:
            try:
                from src.core.factory import get_llm_provider

                llm_provider = get_llm_provider(config)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to create LLM provider: %s", e)

        if graph_provider is None:
            try:
                from src.core.factory import get_graph_provider

                graph_provider = get_graph_provider(config)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to create graph provider: %s", e)

    return Data2NeoExtractor(
        config=config,
        llm_provider=llm_provider,
        graph_provider=graph_provider,
    )
