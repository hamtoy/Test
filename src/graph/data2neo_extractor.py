"""Data2Neo Extractor for OCR text to Neo4j Knowledge Graph.

Phase 2 implementation of the Data2Neo pipeline.
Extracts entities (Person, Organization, Date, DocumentRule) from OCR text
using GeminiAgent for LLM-based extraction.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from src.config import AppConfig
from src.infra.utils import clean_markdown_code_block

from .entities import (
    DateEntity,
    DocumentRule,
    ExtractionResult,
    Organization,
    Person,
    Relationship,
)

if TYPE_CHECKING:
    from src.agent.core import GeminiAgent
    from src.core.interfaces import GraphProvider


class Data2NeoExtractor:
    """Extracts entities from OCR text and creates Neo4j nodes.

    This class implements Phase 2 of the Data2Neo integration:
    - Uses GeminiAgent for LLM-based entity extraction
    - Validates extraction results with confidence thresholds
    - Supports batch processing of documents

    Attributes:
        config: Application configuration
        agent: GeminiAgent instance for LLM calls
        logger: Logger instance
    """

    def __init__(
        self,
        config: AppConfig,
        agent: "GeminiAgent",
        graph_provider: Optional["GraphProvider"] = None,
        jinja_env: Optional[Environment] = None,
    ) -> None:
        """Initialize the Data2NeoExtractor.

        Args:
            config: Application configuration
            agent: GeminiAgent instance for LLM-based extraction
            graph_provider: Optional GraphProvider for writing to Neo4j
            jinja_env: Optional Jinja2 environment (for testing)
        """
        self.config = config
        self.agent = agent
        self.graph_provider = graph_provider
        self.logger = logging.getLogger("Data2NeoExtractor")

        # Initialize Jinja2 environment
        if jinja_env is not None:
            self.jinja_env = jinja_env
        else:
            self.jinja_env = Environment(
                loader=FileSystemLoader(config.template_dir),
                autoescape=True,
            )

        # Statistics
        self._extraction_count = 0
        self._total_entities = 0

    async def extract_entities(
        self,
        ocr_text: str,
        document_path: Optional[str] = None,
        focus_entities: Optional[List[str]] = None,
    ) -> ExtractionResult:
        """Extract entities from OCR text using LLM.

        Args:
            ocr_text: The OCR text to extract entities from
            document_path: Optional path to the source document
            focus_entities: Optional list of entity types to prioritize

        Returns:
            ExtractionResult containing all extracted entities

        Raises:
            ValueError: If OCR text is empty
            ValidationError: If LLM response doesn't match expected schema
        """
        if not ocr_text or not ocr_text.strip():
            raise ValueError("OCR text cannot be empty")

        # Render prompts
        system_prompt = self._render_system_prompt()
        user_prompt = self._render_user_prompt(
            ocr_text, document_path, focus_entities
        )

        # Create model and call API
        model = self.agent._create_generative_model(
            system_prompt, response_schema=ExtractionResult
        )

        try:
            response_text = await self.agent._call_api_with_retry(model, user_prompt)
        except Exception as e:
            self.logger.error("Entity extraction API call failed: %s", e)
            raise

        # Parse and validate response
        result = self._parse_extraction_response(response_text)

        # Apply confidence threshold
        threshold = self.config.data2neo_confidence
        filtered_result = result.filter_by_confidence(threshold)

        # Update statistics
        self._extraction_count += 1
        self._total_entities += filtered_result.total_entities

        self.logger.info(
            "Extracted %d entities (threshold=%.2f) from document",
            filtered_result.total_entities,
            threshold,
        )

        return filtered_result

    def _render_system_prompt(self) -> str:
        """Render the system prompt for entity extraction."""
        schema_json = json.dumps(
            ExtractionResult.model_json_schema(), indent=2, ensure_ascii=False
        )
        template = self.jinja_env.get_template("prompt_entity_extraction.j2")
        return template.render(response_schema=schema_json)

    def _render_user_prompt(
        self,
        ocr_text: str,
        document_path: Optional[str] = None,
        focus_entities: Optional[List[str]] = None,
    ) -> str:
        """Render the user prompt for entity extraction."""
        template = self.jinja_env.get_template("entity_extraction_user.j2")
        return template.render(
            ocr_text=ocr_text,
            document_path=document_path,
            focus_entities=focus_entities,
        )

    def _parse_extraction_response(self, response_text: str) -> ExtractionResult:
        """Parse and validate the LLM response.

        Args:
            response_text: Raw response from LLM

        Returns:
            Validated ExtractionResult

        Raises:
            ValidationError: If response doesn't match schema
        """
        cleaned = clean_markdown_code_block(response_text)

        if not cleaned or not cleaned.strip():
            self.logger.warning("Empty response from entity extraction")
            return ExtractionResult()

        try:
            return ExtractionResult.model_validate_json(cleaned)
        except ValidationError as e:
            self.logger.error("Extraction validation failed: %s", e)
            # Try to parse as raw JSON and extract what we can
            try:
                data = json.loads(cleaned)
                return self._parse_partial_result(data)
            except json.JSONDecodeError:
                self.logger.error("Failed to parse extraction response as JSON")
                raise

    def _parse_partial_result(self, data: Dict[str, Any]) -> ExtractionResult:
        """Attempt to parse partial results from malformed response.

        Args:
            data: Partially parsed JSON data

        Returns:
            ExtractionResult with whatever could be parsed
        """
        result = ExtractionResult()

        # Try to extract each entity type (graceful handling of partial failures)
        for person_data in data.get("persons", []):
            try:
                result.persons.append(Person.model_validate(person_data))
            except ValidationError:  # noqa: PERF203
                self.logger.debug("Skipping invalid person: %s", person_data)

        for org_data in data.get("organizations", []):
            try:
                result.organizations.append(Organization.model_validate(org_data))
            except ValidationError:  # noqa: PERF203
                self.logger.debug("Skipping invalid organization: %s", org_data)

        for date_data in data.get("dates", []):
            try:
                result.dates.append(DateEntity.model_validate(date_data))
            except ValidationError:  # noqa: PERF203
                self.logger.debug("Skipping invalid date: %s", date_data)

        for rule_data in data.get("document_rules", []):
            try:
                result.document_rules.append(DocumentRule.model_validate(rule_data))
            except ValidationError:  # noqa: PERF203
                self.logger.debug("Skipping invalid document rule: %s", rule_data)

        for rel_data in data.get("relationships", []):
            try:
                result.relationships.append(Relationship.model_validate(rel_data))
            except ValidationError:  # noqa: PERF203
                self.logger.debug("Skipping invalid relationship: %s", rel_data)

        return result

    async def write_to_graph(
        self,
        result: ExtractionResult,
        document_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Write extracted entities to Neo4j graph.

        Args:
            result: ExtractionResult to write
            document_id: Optional document identifier for linking

        Returns:
            Dictionary with counts of created nodes/relationships

        Raises:
            RuntimeError: If graph_provider is not configured
        """
        if self.graph_provider is None:
            raise RuntimeError("GraphProvider not configured")

        counts: Dict[str, int] = {
            "persons": 0,
            "organizations": 0,
            "dates": 0,
            "document_rules": 0,
            "relationships": 0,
        }

        batch_size = self.config.data2neo_batch_size

        # Write Person nodes
        if result.persons:
            person_nodes = [p.to_node_dict() for p in result.persons]
            for node in person_nodes:
                node["id"] = self._generate_entity_id("person", node["name"])
            counts["persons"] = await self.graph_provider.create_nodes(
                person_nodes[:batch_size], "Person", merge_on="id"
            )

        # Write Organization nodes
        if result.organizations:
            org_nodes = [o.to_node_dict() for o in result.organizations]
            for node in org_nodes:
                node["id"] = self._generate_entity_id("org", node["name"])
            counts["organizations"] = await self.graph_provider.create_nodes(
                org_nodes[:batch_size], "Organization", merge_on="id"
            )

        # Write Date nodes
        if result.dates:
            date_nodes = [d.to_node_dict() for d in result.dates]
            for node in date_nodes:
                node["id"] = self._generate_entity_id("date", node["name"])
            counts["dates"] = await self.graph_provider.create_nodes(
                date_nodes[:batch_size], "Date", merge_on="id"
            )

        # Write DocumentRule nodes
        if result.document_rules:
            rule_nodes = [r.to_node_dict() for r in result.document_rules]
            for node in rule_nodes:
                node["id"] = self._generate_entity_id("docrule", node["text"])
            counts["document_rules"] = await self.graph_provider.create_nodes(
                rule_nodes[:batch_size], "DocumentRule", merge_on="id"
            )

        # Write relationships
        # Note: Relationship writing requires entity type resolution
        # This is a simplified implementation
        for rel in result.relationships:
            try:
                # Determine source and target labels based on relationship type
                from_label, to_label = self._infer_relationship_labels(rel.rel_type)
                await self.graph_provider.create_relationships(
                    [
                        {
                            "from_id": self._generate_entity_id(
                                from_label.lower(), rel.from_entity
                            ),
                            "to_id": self._generate_entity_id(
                                to_label.lower(), rel.to_entity
                            ),
                            **rel.properties,
                        }
                    ],
                    rel.rel_type,
                    from_label,
                    to_label,
                )
                counts["relationships"] += 1
            except Exception as e:  # noqa: PERF203
                self.logger.warning("Failed to create relationship: %s", e)

        self.logger.info(
            "Wrote entities to graph: %s",
            ", ".join(f"{k}={v}" for k, v in counts.items()),
        )

        return counts

    @staticmethod
    def _generate_entity_id(prefix: str, name: str) -> str:
        """Generate a unique ID for an entity.

        Args:
            prefix: Entity type prefix (person, org, etc.)
            name: Entity name

        Returns:
            Hash-based unique ID
        """
        normalized = name.strip().lower()
        hash_val = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{hash_val}"

    @staticmethod
    def _infer_relationship_labels(rel_type: str) -> tuple[str, str]:
        """Infer source and target labels from relationship type.

        Args:
            rel_type: Relationship type string

        Returns:
            Tuple of (from_label, to_label)
        """
        rel_mappings = {
            "WORKS_AT": ("Person", "Organization"),
            "MEMBER_OF": ("Person", "Organization"),
            "FOUNDED": ("Person", "Organization"),
            "PUBLISHED_ON": ("Document", "Date"),
            "REFERENCES": ("DocumentRule", "Document"),
            "ENFORCES": ("DocumentRule", "Organization"),
        }
        return rel_mappings.get(rel_type, ("Entity", "Entity"))

    def get_statistics(self) -> Dict[str, int]:
        """Get extraction statistics.

        Returns:
            Dictionary with extraction counts
        """
        return {
            "extraction_count": self._extraction_count,
            "total_entities": self._total_entities,
        }
