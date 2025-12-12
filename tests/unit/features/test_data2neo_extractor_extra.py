"""Extra tests for Data2NeoExtractor edge branches."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.features.data2neo_extractor import Data2NeoExtractor, ExtractionResult


@pytest.mark.asyncio
async def test_extract_entities_without_llm_provider_returns_empty() -> None:
    config = MagicMock()
    config.data2neo_confidence = 0.7
    config.data2neo_batch_size = 10
    extractor = Data2NeoExtractor(config=config, llm_provider=None, graph_provider=None)

    result = await extractor.extract_entities("text", "doc_1")
    assert result.entities == []
    assert result.document_id == "doc_1"


@pytest.mark.asyncio
async def test_import_to_graph_without_graph_provider_returns_zero() -> None:
    config = MagicMock()
    config.data2neo_confidence = 0.7
    config.data2neo_batch_size = 10
    extractor = Data2NeoExtractor(config=config, llm_provider=None, graph_provider=None)

    counts = await extractor.import_to_graph(ExtractionResult(document_id="doc_1"))
    assert counts == {"nodes": 0, "relationships": 0}
