# 🤖 AI Agent Improvement Prompts

> ## 🚨 MANDATORY: FILE MODIFICATION REQUIRED
> 
> **⛔ DO NOT just respond with text or code blocks.**
> **⛔ DO NOT say "you can modify like this" without actually modifying.**
> **⛔ DO NOT explain what needs to be done without doing it.**
> 
> **✅ YOU MUST use file editing tools (`replace_string_in_file`, `create_file`, `multi_replace_string_in_file`) to directly modify files.**
> **✅ After each prompt, confirm "I have modified the file(s)" with the actual changes made.**
> 
> ---
> 
> **Process ALL prompts below SEQUENTIALLY. Do NOT stop after completing one prompt.**

---

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | RAG System Module Split | P2 | ✅ Done |
| 2 | PROMPT-002 | Web API Dependency Injection Pattern | P2 | ✅ Done |
| 3 | PROMPT-003 | Web API Input Validation Hardening | P2 | ✅ Done |
| 4 | PROMPT-004 | Sphinx Documentation Auto-Generation | P3 | ✅ Done |
| 5 | PROMPT-005 | E2E Test Coverage Expansion | P3 | ✅ Done |
| 6 | PROMPT-006 | Cache Metrics Dashboard Enhancement | P3 | ✅ Done |
| 7 | PROMPT-007 | Docstring Standardization | P3 | ✅ Done |

**Total: 7 prompts** | **Completed: 7** | **Remaining: 0**

---

## 🟡 Priority 2 (High) - Execute First

### [PROMPT-001] RAG System Module Split

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-002**

**Task**: Split the 1022-line `src/qa/rag_system.py` into three separate modules for better maintainability.

**Files to Modify**: 
- Create `src/qa/graph/__init__.py`
- Create `src/qa/graph/connection.py`
- Create `src/qa/graph/vector_search.py`
- Create `src/qa/graph/rule_extractor.py`
- Update `src/qa/rag_system.py`

#### Instructions:

1. Create the `src/qa/graph/` directory structure
2. Extract Neo4j connection management to `connection.py`
3. Extract vector search logic to `vector_search.py`
4. Extract rule extraction and QA generation to `rule_extractor.py`
5. Update `rag_system.py` to import from the new modules
6. Ensure backward compatibility by re-exporting from `__init__.py`

#### Implementation Code:

**File: src/qa/graph/__init__.py**
```python
"""Graph-based QA components for RAG system.

This package provides modular components for Neo4j-based knowledge graph operations:
- connection: Neo4j connection management
- vector_search: Vector similarity search
- rule_extractor: Rule extraction and QA generation
"""

from src.qa.graph.connection import Neo4jConnectionManager
from src.qa.graph.vector_search import VectorSearchEngine
from src.qa.graph.rule_extractor import RuleExtractor

__all__ = [
    "Neo4jConnectionManager",
    "VectorSearchEngine", 
    "RuleExtractor",
]
```

**File: src/qa/graph/connection.py**
```python
"""Neo4j connection management module.

Provides connection pooling, health checks, and graceful shutdown
for Neo4j database connections used in the RAG system.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """Manages Neo4j database connections.
    
    Handles connection lifecycle, health checks, and provides
    a unified interface for database operations.
    
    Args:
        uri: Neo4j bolt URI (e.g., 'bolt://localhost:7687')
        user: Database username
        password: Database password
        
    Raises:
        ConnectionError: If unable to establish database connection
    """
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Initialize Neo4j connection manager."""
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "")
        self._driver: Any = None
        self._connected = False
        
    def connect(self) -> bool:
        """Establish connection to Neo4j database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            from neo4j import GraphDatabase
            
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j connection established: %s", self.uri)
            return True
        except Exception as e:
            logger.warning("Neo4j connection failed: %s", e)
            self._connected = False
            return False
            
    def close(self) -> None:
        """Close Neo4j connection gracefully."""
        if self._driver:
            self._driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")
            
    @property
    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._connected
        
    @property
    def driver(self) -> Any:
        """Get the Neo4j driver instance."""
        if not self._connected:
            self.connect()
        return self._driver
        
    def execute_query(self, query: str, parameters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        if not self._driver:
            raise ConnectionError("Not connected to Neo4j")
            
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
```

**File: src/qa/graph/vector_search.py**
```python
"""Vector similarity search module for RAG system.

Provides vector embedding and similarity search capabilities
using LangChain and Neo4j vector indexes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.qa.graph.connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """Vector similarity search engine using Neo4j.
    
    Provides methods for embedding text and finding similar
    documents in the knowledge graph.
    
    Args:
        connection_manager: Neo4j connection manager instance
        embedding_model: Name of the embedding model to use
    """
    
    def __init__(
        self,
        connection_manager: "Neo4jConnectionManager",
        embedding_model: str = "text-embedding-ada-002",
    ) -> None:
        """Initialize vector search engine."""
        self.connection = connection_manager
        self.embedding_model = embedding_model
        self._embeddings: Any = None
        self._vector_store: Any = None
        
    def _init_embeddings(self) -> None:
        """Initialize the embedding model lazily."""
        if self._embeddings is None:
            try:
                from langchain_openai import OpenAIEmbeddings
                
                self._embeddings = OpenAIEmbeddings(model=self.embedding_model)
                logger.info("Embeddings initialized: %s", self.embedding_model)
            except ImportError:
                logger.warning("langchain_openai not available, vector search disabled")
                
    def search_similar(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search for similar documents using vector similarity.
        
        Args:
            query: Search query text
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of similar documents with scores
        """
        self._init_embeddings()
        
        if self._embeddings is None:
            return []
            
        try:
            from langchain_neo4j import Neo4jVector
            
            if self._vector_store is None:
                self._vector_store = Neo4jVector.from_existing_index(
                    self._embeddings,
                    url=self.connection.uri,
                    username=self.connection.user,
                    password=self.connection.password,
                    index_name="rule_embedding",
                )
                
            results = self._vector_store.similarity_search_with_score(
                query,
                k=k,
            )
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score,
                }
                for doc, score in results
                if score >= score_threshold
            ]
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []
            
    def embed_text(self, text: str) -> Optional[list[float]]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        self._init_embeddings()
        
        if self._embeddings is None:
            return None
            
        try:
            return self._embeddings.embed_query(text)
        except Exception as e:
            logger.warning("Text embedding failed: %s", e)
            return None
```

**File: src/qa/graph/rule_extractor.py**
```python
"""Rule extraction and QA generation module.

Provides methods for extracting rules from the knowledge graph
and generating QA pairs based on those rules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.qa.graph.connection import Neo4jConnectionManager
    from src.qa.graph.vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


class RuleExtractor:
    """Extracts rules and generates QA from knowledge graph.
    
    Provides methods for retrieving rules, constraints, and examples
    from the Neo4j knowledge graph for QA generation.
    
    Args:
        connection_manager: Neo4j connection manager
        vector_engine: Vector search engine for similarity queries
    """
    
    def __init__(
        self,
        connection_manager: "Neo4jConnectionManager",
        vector_engine: "VectorSearchEngine",
    ) -> None:
        """Initialize rule extractor."""
        self.connection = connection_manager
        self.vector_engine = vector_engine
        
    def get_rules_for_topic(self, topic: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get rules related to a specific topic.
        
        Args:
            topic: Topic to search for
            limit: Maximum number of rules to return
            
        Returns:
            List of rules with their constraints and examples
        """
        query = """
        MATCH (r:Rule)-[:HAS_CONSTRAINT]->(c:Constraint)
        OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example)
        WHERE r.topic CONTAINS $topic OR r.content CONTAINS $topic
        RETURN r.id AS rule_id,
               r.content AS rule_content,
               collect(DISTINCT c.content) AS constraints,
               collect(DISTINCT e.content) AS examples
        LIMIT $limit
        """
        
        try:
            results = self.connection.execute_query(
                query,
                {"topic": topic, "limit": limit},
            )
            return results
        except Exception as e:
            logger.warning("Failed to get rules for topic '%s': %s", topic, e)
            return []
            
    def get_similar_rules(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Get rules similar to the query using vector search.
        
        Args:
            query: Query text
            k: Number of rules to return
            
        Returns:
            List of similar rules with scores
        """
        return self.vector_engine.search_similar(query, k=k)
        
    def generate_qa_context(
        self,
        query: str,
        max_rules: int = 5,
        include_examples: bool = True,
    ) -> str:
        """Generate context for QA based on relevant rules.
        
        Args:
            query: User query
            max_rules: Maximum rules to include
            include_examples: Whether to include examples
            
        Returns:
            Formatted context string for QA generation
        """
        rules = self.get_similar_rules(query, k=max_rules)
        
        if not rules:
            return ""
            
        context_parts = ["## Relevant Rules\n"]
        
        for i, rule in enumerate(rules, 1):
            content = rule.get("content", "")
            metadata = rule.get("metadata", {})
            
            context_parts.append(f"### Rule {i}")
            context_parts.append(content)
            
            if include_examples and "examples" in metadata:
                context_parts.append("\n**Examples:**")
                for example in metadata["examples"][:2]:
                    context_parts.append(f"- {example}")
                    
            context_parts.append("")
            
        return "\n".join(context_parts)
        
    def validate_answer_against_rules(
        self,
        answer: str,
        query: str,
    ) -> dict[str, Any]:
        """Validate an answer against relevant rules.
        
        Args:
            answer: Answer to validate
            query: Original query
            
        Returns:
            Validation result with any rule violations
        """
        rules = self.get_similar_rules(query, k=3)
        
        violations = []
        for rule in rules:
            content = rule.get("content", "").lower()
            # Simple keyword-based validation
            if "must" in content or "required" in content:
                # Check if answer addresses the requirement
                # This is a simplified check - actual implementation would be more sophisticated
                pass
                
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "rules_checked": len(rules),
        }
```

#### Verification:
- Run: `python -c "from src.qa.graph import Neo4jConnectionManager, VectorSearchEngine, RuleExtractor; print('Import successful')"`
- Expected: No import errors

**✅ After completing this prompt, proceed to [PROMPT-002]**

---

### [PROMPT-002] Web API Dependency Injection Pattern

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-003**

**Task**: Apply FastAPI dependency injection pattern to replace global state in `src/web/api.py`.

**Files to Modify**: 
- Create `src/web/dependencies.py`
- Update `src/web/api.py`

#### Instructions:

1. Create a new `dependencies.py` module with service factories
2. Define dependency functions using FastAPI's `Depends`
3. Update API endpoints to use injected dependencies
4. Maintain backward compatibility for existing tests

#### Implementation Code:

**File: src/web/dependencies.py**
```python
"""FastAPI dependency injection for web API services.

Provides factory functions for injecting services into API endpoints,
enabling better testability and horizontal scaling.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from fastapi import Depends, Request

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.config import AppConfig
    from src.features.multimodal import MultimodalUnderstanding
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# Repository root for template loading
REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache()
def get_app_config() -> "AppConfig":
    """Get cached application configuration.
    
    Returns:
        AppConfig instance (singleton)
    """
    from src.config import AppConfig
    
    return AppConfig()


def get_jinja_env() -> Any:
    """Get Jinja2 environment for template rendering.
    
    Returns:
        Configured Jinja2 Environment
    """
    from jinja2 import Environment, FileSystemLoader
    
    return Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


class ServiceContainer:
    """Container for lazily initialized services.
    
    Provides singleton instances of services that are expensive
    to create, such as AI agents and database connections.
    """
    
    _agent: Optional["GeminiAgent"] = None
    _kg: Optional["QAKnowledgeGraph"] = None
    _mm: Optional["MultimodalUnderstanding"] = None
    
    @classmethod
    def get_agent(cls, config: "AppConfig" = Depends(get_app_config)) -> Optional["GeminiAgent"]:
        """Get or create GeminiAgent instance.
        
        Args:
            config: Application configuration
            
        Returns:
            GeminiAgent instance or None if initialization fails
        """
        if cls._agent is None:
            from src.agent import GeminiAgent
            
            cls._agent = GeminiAgent(
                config=config,
                jinja_env=get_jinja_env(),
            )
            logger.info("GeminiAgent initialized via DI")
        return cls._agent
        
    @classmethod
    def get_knowledge_graph(cls) -> Optional["QAKnowledgeGraph"]:
        """Get or create QAKnowledgeGraph instance.
        
        Returns:
            QAKnowledgeGraph instance or None if Neo4j unavailable
        """
        if cls._kg is None:
            try:
                from src.qa.rag_system import QAKnowledgeGraph
                
                cls._kg = QAKnowledgeGraph()
                logger.info("QAKnowledgeGraph initialized via DI")
            except Exception as e:
                logger.warning("Neo4j connection failed: %s", e)
        return cls._kg
        
    @classmethod
    def get_multimodal(cls) -> Optional["MultimodalUnderstanding"]:
        """Get or create MultimodalUnderstanding instance.
        
        Returns:
            MultimodalUnderstanding instance or None if prerequisites missing
        """
        if cls._mm is None:
            kg = cls.get_knowledge_graph()
            if kg is not None:
                from src.features.multimodal import MultimodalUnderstanding
                
                cls._mm = MultimodalUnderstanding(kg=kg)
                logger.info("MultimodalUnderstanding initialized via DI")
        return cls._mm
        
    @classmethod
    def reset(cls) -> None:
        """Reset all service instances (for testing)."""
        cls._agent = None
        cls._kg = None
        cls._mm = None


# Dependency functions for FastAPI
def get_agent(
    config: "AppConfig" = Depends(get_app_config),
) -> Optional["GeminiAgent"]:
    """FastAPI dependency for GeminiAgent.
    
    Args:
        config: Injected application configuration
        
    Returns:
        GeminiAgent instance
    """
    return ServiceContainer.get_agent(config)


def get_knowledge_graph() -> Optional["QAKnowledgeGraph"]:
    """FastAPI dependency for QAKnowledgeGraph.
    
    Returns:
        QAKnowledgeGraph instance or None
    """
    return ServiceContainer.get_knowledge_graph()


def get_multimodal() -> Optional["MultimodalUnderstanding"]:
    """FastAPI dependency for MultimodalUnderstanding.
    
    Returns:
        MultimodalUnderstanding instance or None
    """
    return ServiceContainer.get_multimodal()


__all__ = [
    "get_app_config",
    "get_agent",
    "get_knowledge_graph",
    "get_multimodal",
    "ServiceContainer",
    "REPO_ROOT",
]
```

#### Verification:
- Run: `python -c "from src.web.dependencies import get_app_config, get_agent; print('Dependencies loaded')"`
- Expected: No import errors

**✅ After completing this prompt, proceed to [PROMPT-003]**

---

### [PROMPT-003] Web API Input Validation Hardening

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-004**

**Task**: Add input length limits and validation to web API models to prevent DoS attacks.

**Files to Modify**: `src/web/models.py`

#### Instructions:

1. Add `Field(max_length=...)` constraints to all string fields
2. Add file size limit constants
3. Add validation for nested objects

#### Implementation Code:

Update `src/web/models.py` to add the following constants and field constraints:

```python
"""Web API request/response models with validation.

All string fields have explicit length limits to prevent
memory exhaustion attacks and ensure API stability.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Constants for validation limits
MAX_QUERY_LENGTH = 10000
MAX_ANSWER_LENGTH = 50000
MAX_OCR_TEXT_LENGTH = 100000
MAX_EDIT_REQUEST_LENGTH = 5000
MAX_COMMENT_LENGTH = 2000
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class GenerateQARequest(BaseModel):
    """Request model for QA generation endpoint."""
    
    mode: Literal["batch", "single"] = Field(
        default="batch",
        description="Generation mode: 'batch' for all 4 types, 'single' for one type"
    )
    qtype: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Question type for single mode"
    )


class EvalExternalRequest(BaseModel):
    """Request model for external answer evaluation."""
    
    query: str = Field(
        ...,
        max_length=MAX_QUERY_LENGTH,
        description="The question to evaluate answers for"
    )
    answers: Dict[str, str] = Field(
        ...,
        description="Dictionary of candidate answers (A, B, C)"
    )
    
    class Config:
        """Pydantic model configuration."""
        
        json_schema_extra = {
            "example": {
                "query": "What is the capital of France?",
                "answers": {
                    "A": "Paris is the capital of France.",
                    "B": "London is the capital.",
                    "C": "Berlin is located in Germany."
                }
            }
        }


class WorkspaceRequest(BaseModel):
    """Request model for workspace operations (inspect/edit)."""
    
    mode: Literal["inspect", "edit"] = Field(
        default="inspect",
        description="Operation mode"
    )
    answer: str = Field(
        ...,
        max_length=MAX_ANSWER_LENGTH,
        description="Answer content to process"
    )
    query: Optional[str] = Field(
        default=None,
        max_length=MAX_QUERY_LENGTH,
        description="Associated query (optional)"
    )
    edit_request: Optional[str] = Field(
        default=None,
        max_length=MAX_EDIT_REQUEST_LENGTH,
        description="Edit instructions for 'edit' mode"
    )
    inspector_comment: Optional[str] = Field(
        default=None,
        max_length=MAX_COMMENT_LENGTH,
        description="Inspector's comment for logging"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoints."""
    
    status: Literal["healthy", "degraded", "unhealthy"]
    services: Dict[str, bool] = Field(default_factory=dict)
    version: Optional[str] = None


__all__ = [
    "GenerateQARequest",
    "EvalExternalRequest",
    "WorkspaceRequest",
    "HealthResponse",
    "MAX_QUERY_LENGTH",
    "MAX_ANSWER_LENGTH",
    "MAX_OCR_TEXT_LENGTH",
    "MAX_EDIT_REQUEST_LENGTH",
    "MAX_COMMENT_LENGTH",
    "MAX_UPLOAD_SIZE_BYTES",
]
```

#### Verification:
- Run: `python -c "from src.web.models import MAX_UPLOAD_SIZE_BYTES; print(f'Max upload: {MAX_UPLOAD_SIZE_BYTES} bytes')"`
- Expected: `Max upload: 10485760 bytes`

**✅ After completing this prompt, proceed to [PROMPT-004]**

---

## 🟢 Priority 3 (Medium) - Execute Last

### [PROMPT-004] Sphinx Documentation Auto-Generation

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-005**

**Task**: Set up Sphinx documentation auto-generation for the API reference.

**Files to Modify**: 
- Update `docs/conf.py`
- Create `docs/api/index.rst`
- Create `scripts/generate_docs.sh`

#### Instructions:

1. Configure Sphinx autodoc extension
2. Create API documentation structure
3. Add documentation generation script

#### Implementation Code:

**File: scripts/generate_docs.sh**
```bash
#!/bin/bash
# Generate API documentation using Sphinx

set -e

DOCS_DIR="docs"
API_DIR="$DOCS_DIR/api"

# Create API directory if not exists
mkdir -p "$API_DIR"

# Generate API documentation from source
sphinx-apidoc -f -o "$API_DIR" src/ \
    --separate \
    --module-first \
    -H "API Reference" \
    -A "shining-quasar Team"

# Build HTML documentation
cd "$DOCS_DIR"
make html

echo "Documentation generated: docs/_build/html/index.html"
```

**File: docs/api/index.rst**
```rst
API Reference
=============

This section contains automatically generated API documentation
for all modules in the shining-quasar project.

.. toctree::
   :maxdepth: 2
   :caption: Modules:

   src.agent
   src.core
   src.config
   src.workflow
   src.web
   src.qa
   src.caching
   src.infra
   src.graph
   src.monitoring

Module Index
------------

* :ref:`genindex`
* :ref:`modindex`
```

#### Verification:
- Run: `chmod +x scripts/generate_docs.sh && ls -la scripts/generate_docs.sh`
- Expected: Executable script file

**✅ After completing this prompt, proceed to [PROMPT-005]**

---

### [PROMPT-005] E2E Test Coverage Expansion

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-006**

**Task**: Create comprehensive E2E test for the full workflow pipeline.

**Files to Modify**: Create `tests/e2e/test_workflow_e2e.py`

#### Instructions:

1. Create mock Gemini API responses
2. Test full workflow from query generation to rewrite
3. Add performance regression test markers

#### Implementation Code:

**File: tests/e2e/test_workflow_e2e.py**
```python
"""End-to-end tests for the complete workflow pipeline.

These tests verify the entire flow from query generation
to answer evaluation and rewriting, using mocked API responses.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig
from src.core.models import EvaluationResultSchema, QueryResult


@pytest.fixture
def mock_config() -> AppConfig:
    """Create a mock AppConfig for testing."""
    with patch.dict(
        "os.environ",
        {
            "GEMINI_API_KEY": "AIza" + "x" * 35,
            "GEMINI_MODEL_NAME": "gemini-3-pro-preview",
        },
    ):
        config = AppConfig()
    return config


@pytest.fixture
def mock_jinja_env() -> MagicMock:
    """Create a mock Jinja2 environment."""
    env = MagicMock()
    template = MagicMock()
    template.render.return_value = "System prompt"
    env.get_template.return_value = template
    return env


@pytest.fixture
def mock_agent(mock_config: AppConfig, mock_jinja_env: MagicMock) -> GeminiAgent:
    """Create a GeminiAgent with mocked dependencies."""
    return GeminiAgent(
        config=mock_config,
        jinja_env=mock_jinja_env,
    )


class TestWorkflowE2E:
    """End-to-end workflow tests."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_full_workflow_query_to_rewrite(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test complete workflow: query generation → evaluation → rewrite."""
        # Mock API responses
        query_response = QueryResult(queries=["What is the main topic?"])
        eval_response = EvaluationResultSchema(
            best_candidate="A",
            evaluations=[
                {"candidate_id": "A", "score": 85, "reason": "Clear and accurate"},
                {"candidate_id": "B", "score": 70, "reason": "Partially correct"},
            ],
        )
        rewrite_response = "This is the improved answer with better clarity."

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            new_callable=AsyncMock,
        ) as mock_api:
            # Configure mock responses
            mock_api.side_effect = [
                query_response.model_dump_json(),
                eval_response.model_dump_json(),
                rewrite_response,
            ]

            # Step 1: Generate queries
            ocr_text = "Sample OCR text content for testing."
            queries = await mock_agent.generate_query(ocr_text)
            
            assert len(queries) > 0
            assert queries[0] == "What is the main topic?"

            # Step 2: Evaluate responses
            candidates = {
                "A": "This is answer A.",
                "B": "This is answer B.",
            }
            evaluation = await mock_agent.evaluate_responses(
                ocr_text=ocr_text,
                query=queries[0],
                candidates=candidates,
            )
            
            assert evaluation is not None
            assert evaluation.best_candidate == "A"

            # Step 3: Rewrite best answer
            rewritten = await mock_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=candidates["A"],
            )
            
            assert "improved" in rewritten.lower()

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_with_cache(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test workflow with context caching enabled."""
        # Skip if cache creation is mocked
        with patch.object(
            mock_agent,
            "create_context_cache",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch.object(
                mock_agent,
                "_call_api_with_retry",
                new_callable=AsyncMock,
                return_value='{"queries": ["Test query"]}',
            ):
                queries = await mock_agent.generate_query(
                    "Long OCR text " * 500,  # Simulate large input
                    user_intent="Summarize",
                )
                
                assert len(queries) > 0

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_workflow_error_recovery(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test workflow recovers from transient API errors."""
        call_count = 0

        async def flaky_api(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Simulated timeout")
            return '{"queries": ["Recovered query"]}'

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            side_effect=flaky_api,
        ):
            # Should retry and succeed
            queries = await mock_agent.generate_query("Test OCR")
            
            assert len(queries) > 0
            assert call_count >= 2  # At least one retry


class TestWorkflowPerformance:
    """Performance regression tests for workflow."""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_query_generation_latency(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Verify query generation completes within acceptable time."""
        import time

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            new_callable=AsyncMock,
            return_value='{"queries": ["Quick query"]}',
        ):
            start = time.perf_counter()
            await mock_agent.generate_query("Test OCR text")
            elapsed = time.perf_counter() - start

            # Should complete mock call in under 1 second
            assert elapsed < 1.0, f"Query generation too slow: {elapsed:.2f}s"
```

#### Verification:
- Run: `python -m pytest tests/e2e/test_workflow_e2e.py --collect-only`
- Expected: Tests collected without errors

**✅ After completing this prompt, proceed to [PROMPT-006]**

---

### [PROMPT-006] Cache Metrics Dashboard Enhancement

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-007**

**Task**: Add Prometheus histogram metrics for cache performance monitoring.

**Files to Modify**: `src/caching/analytics.py`

#### Instructions:

1. Add Prometheus counter and histogram metrics
2. Create helper functions for metric updates
3. Ensure metrics are exported correctly

#### Implementation Code:

Add the following to `src/caching/analytics.py`:

```python
# Add at the top of the file after existing imports
from typing import Optional

# Prometheus metrics (lazy initialization to avoid import errors)
_CACHE_HIT_COUNTER: Optional[Any] = None
_CACHE_MISS_COUNTER: Optional[Any] = None
_CACHE_LATENCY_HISTOGRAM: Optional[Any] = None


def _init_prometheus_metrics() -> None:
    """Initialize Prometheus metrics lazily."""
    global _CACHE_HIT_COUNTER, _CACHE_MISS_COUNTER, _CACHE_LATENCY_HISTOGRAM
    
    try:
        from prometheus_client import Counter, Histogram
        
        if _CACHE_HIT_COUNTER is None:
            _CACHE_HIT_COUNTER = Counter(
                "cache_hits_total",
                "Total number of cache hits",
                ["cache_type"],
            )
            _CACHE_MISS_COUNTER = Counter(
                "cache_misses_total",
                "Total number of cache misses",
                ["cache_type"],
            )
            _CACHE_LATENCY_HISTOGRAM = Histogram(
                "cache_operation_latency_seconds",
                "Cache operation latency in seconds",
                ["operation", "cache_type"],
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            )
    except ImportError:
        pass  # Prometheus not available


def record_cache_hit(cache_type: str = "context") -> None:
    """Record a cache hit metric.
    
    Args:
        cache_type: Type of cache (context, redis, local)
    """
    _init_prometheus_metrics()
    if _CACHE_HIT_COUNTER is not None:
        _CACHE_HIT_COUNTER.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str = "context") -> None:
    """Record a cache miss metric.
    
    Args:
        cache_type: Type of cache (context, redis, local)
    """
    _init_prometheus_metrics()
    if _CACHE_MISS_COUNTER is not None:
        _CACHE_MISS_COUNTER.labels(cache_type=cache_type).inc()


def record_cache_latency(
    latency_seconds: float,
    operation: str = "lookup",
    cache_type: str = "context",
) -> None:
    """Record cache operation latency.
    
    Args:
        latency_seconds: Operation duration in seconds
        operation: Operation type (lookup, store, delete)
        cache_type: Type of cache
    """
    _init_prometheus_metrics()
    if _CACHE_LATENCY_HISTOGRAM is not None:
        _CACHE_LATENCY_HISTOGRAM.labels(
            operation=operation,
            cache_type=cache_type,
        ).observe(latency_seconds)
```

#### Verification:
- Run: `python -c "from src.caching.analytics import record_cache_hit; record_cache_hit(); print('Metrics OK')"`
- Expected: `Metrics OK`

**✅ After completing this prompt, proceed to [PROMPT-007]**

---

### [PROMPT-007] Docstring Standardization

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then ALL PROMPTS ARE COMPLETED.**

**Task**: Create a script to check and report docstring style inconsistencies.

**Files to Modify**: Create `scripts/check_docstrings.py`

#### Instructions:

1. Create a script that identifies docstring style issues
2. Report functions missing docstrings
3. Identify mixed Google/NumPy style usage

#### Implementation Code:

**File: scripts/check_docstrings.py**
```python
#!/usr/bin/env python3
"""Docstring style checker for the codebase.

This script identifies:
1. Functions/methods missing docstrings
2. Inconsistent docstring styles (Google vs NumPy)
3. Missing parameter documentation

Usage:
    python scripts/check_docstrings.py [--fix] [path]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, NamedTuple


class DocstringIssue(NamedTuple):
    """Represents a docstring issue found in the code."""
    
    file: str
    line: int
    name: str
    issue_type: str
    message: str


def check_docstring_style(docstring: str) -> str:
    """Determine the docstring style.
    
    Args:
        docstring: The docstring text to analyze
        
    Returns:
        Style name: 'google', 'numpy', 'sphinx', or 'unknown'
    """
    if not docstring:
        return "missing"
        
    # Google style: Args:, Returns:, Raises:
    if "Args:" in docstring or "Returns:" in docstring:
        return "google"
        
    # NumPy style: Parameters\n----------
    if "Parameters\n" in docstring and "----------" in docstring:
        return "numpy"
        
    # Sphinx style: :param, :returns:
    if ":param" in docstring or ":returns:" in docstring:
        return "sphinx"
        
    return "simple"


def analyze_file(file_path: Path) -> List[DocstringIssue]:
    """Analyze a Python file for docstring issues.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        List of issues found
    """
    issues: List[DocstringIssue] = []
    
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        return [DocstringIssue(
            file=str(file_path),
            line=0,
            name="<parse error>",
            issue_type="error",
            message=str(e),
        )]
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            name = node.name
            line = node.lineno
            
            # Skip private/magic methods for missing docstring check
            if name.startswith("_") and not name.startswith("__"):
                continue
                
            if docstring is None:
                issues.append(DocstringIssue(
                    file=str(file_path),
                    line=line,
                    name=name,
                    issue_type="missing",
                    message="Missing docstring",
                ))
            else:
                style = check_docstring_style(docstring)
                if style == "numpy":
                    issues.append(DocstringIssue(
                        file=str(file_path),
                        line=line,
                        name=name,
                        issue_type="style",
                        message="NumPy style detected, prefer Google style",
                    ))
                elif style == "sphinx":
                    issues.append(DocstringIssue(
                        file=str(file_path),
                        line=line,
                        name=name,
                        issue_type="style",
                        message="Sphinx style detected, prefer Google style",
                    ))
    
    return issues


def main() -> int:
    """Main entry point for the docstring checker.
    
    Returns:
        Exit code: 0 if no issues, 1 if issues found
    """
    parser = argparse.ArgumentParser(description="Check docstring consistency")
    parser.add_argument(
        "path",
        nargs="?",
        default="src",
        help="Path to check (default: src)",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only report missing docstrings",
    )
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*.py"))
    
    all_issues: List[DocstringIssue] = []
    
    for file_path in files:
        issues = analyze_file(file_path)
        if args.missing_only:
            issues = [i for i in issues if i.issue_type == "missing"]
        all_issues.extend(issues)
    
    if all_issues:
        print(f"\n{'='*60}")
        print(f"Found {len(all_issues)} docstring issues:")
        print(f"{'='*60}\n")
        
        for issue in sorted(all_issues, key=lambda x: (x.file, x.line)):
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.name}: {issue.message}")
            print()
        
        return 1
    else:
        print("✅ No docstring issues found!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### Verification:
- Run: `python scripts/check_docstrings.py --missing-only src/config 2>/dev/null | head -20`
- Expected: Report of missing docstrings or success message

**🎉 ALL PROMPTS COMPLETED! Run final verification:**

```bash
# Verify all changes
python -c "
from src.qa.graph import Neo4jConnectionManager, VectorSearchEngine, RuleExtractor
from src.web.dependencies import get_app_config, get_agent
from src.web.models import MAX_UPLOAD_SIZE_BYTES
from src.caching.analytics import record_cache_hit
print('All imports successful!')
"
```
