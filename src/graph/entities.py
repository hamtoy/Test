"""Entity models for Data2Neo extraction.

Defines Pydantic models for entities extracted from OCR text,
including Person, Organization, Date, and DocumentRule.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """Base model for all extracted entities."""

    name: str = Field(..., description="Entity name or identifier")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)",
    )
    source_text: str | None = Field(
        None,
        description="Original text span where entity was found",
    )


class Person(ExtractedEntity):
    """Person entity extracted from document."""

    role: str | None = Field(None, description="Role or title of the person")
    organization: str | None = Field(
        None,
        description="Associated organization name",
    )

    def to_node_dict(self) -> dict[str, Any]:
        """Convert to Neo4j node properties dictionary."""
        return {
            "name": self.name,
            "role": self.role,
            "confidence": self.confidence,
        }


class Organization(ExtractedEntity):
    """Organization entity extracted from document."""

    org_type: str | None = Field(
        None,
        description="Type of organization (company, government, NGO, etc.)",
    )
    location: str | None = Field(None, description="Location or headquarters")

    def to_node_dict(self) -> dict[str, Any]:
        """Convert to Neo4j node properties dictionary."""
        return {
            "name": self.name,
            "type": self.org_type,
            "location": self.location,
            "confidence": self.confidence,
        }


class DateEntity(ExtractedEntity):
    """Date entity extracted from document."""

    date_type: str | None = Field(
        None,
        description="Type of date (event, deadline, publication, etc.)",
    )
    normalized: str | None = Field(
        None,
        description="Normalized date format (YYYY-MM-DD)",
    )

    def to_node_dict(self) -> dict[str, Any]:
        """Convert to Neo4j node properties dictionary."""
        return {
            "name": self.name,
            "type": self.date_type,
            "normalized": self.normalized,
            "confidence": self.confidence,
        }


class DocumentRule(ExtractedEntity):
    """Document rule entity extracted from document.

    Note: Named 'DocumentRule' to avoid conflict with existing 'Rule' nodes
    used by the QA system.
    """

    priority: str = Field("normal", description="Priority level (high, normal, low)")
    category: str | None = Field(None, description="Rule category or section")

    def to_node_dict(self) -> dict[str, Any]:
        """Convert to Neo4j node properties dictionary."""
        return {
            "text": self.name,
            "priority": self.priority,
            "category": self.category,
            "confidence": self.confidence,
        }


class Relationship(BaseModel):
    """Relationship between two entities."""

    from_entity: str = Field(..., description="Source entity name")
    to_entity: str = Field(..., description="Target entity name")
    rel_type: str = Field(..., description="Relationship type (e.g., WORKS_AT)")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional relationship properties",
    )


class ExtractionResult(BaseModel):
    """Result of entity extraction from a document."""

    persons: list[Person] = Field(default_factory=list)
    organizations: list[Organization] = Field(default_factory=list)
    dates: list[DateEntity] = Field(default_factory=list)
    document_rules: list[DocumentRule] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    @property
    def total_entities(self) -> int:
        """Total number of entities extracted."""
        return (
            len(self.persons)
            + len(self.organizations)
            + len(self.dates)
            + len(self.document_rules)
        )

    def filter_by_confidence(self, threshold: float) -> ExtractionResult:
        """Filter entities by confidence threshold.

        Args:
            threshold: Minimum confidence score (0.0-1.0)

        Returns:
            New ExtractionResult with only entities meeting the threshold
        """
        return ExtractionResult(
            persons=[p for p in self.persons if p.confidence >= threshold],
            organizations=[o for o in self.organizations if o.confidence >= threshold],
            dates=[d for d in self.dates if d.confidence >= threshold],
            document_rules=[
                r for r in self.document_rules if r.confidence >= threshold
            ],
            relationships=self.relationships,  # Keep all relationships for now
        )
