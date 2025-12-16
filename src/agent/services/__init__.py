"""Agent services package.

This package contains service classes that encapsulate business logic
extracted from GeminiAgent to reduce core responsibilities.

Service Classes:
    - QueryGeneratorService: Handles query generation from OCR text
    - ResponseEvaluatorService: Handles candidate answer evaluation
    - RewriterService: Handles answer rewriting and improvement

Shared Utilities:
    - call_model_with_rate_limit_handling: Rate limit aware API calls
    - load_guide_context_shared: Load guide rules from Neo4j
"""

# Also export shared utilities for advanced use cases
from src.agent.services._utils import (
    call_model_with_rate_limit_handling,
    load_guide_context_shared,
)
from src.agent.services.query_generator import QueryGeneratorService
from src.agent.services.response_evaluator import ResponseEvaluatorService
from src.agent.services.rewriter import RewriterService
from src.config.exceptions import APIRateLimitError, ValidationFailedError
from src.core.models import (
    EvaluationResultSchema,
    QueryResult,
    StructuredAnswerSchema,
)
from src.infra.utils import clean_markdown_code_block, safe_json_parse

__all__ = [
    # Service classes
    "QueryGeneratorService",
    "ResponseEvaluatorService",
    "RewriterService",
    # Shared utilities
    "call_model_with_rate_limit_handling",
    "load_guide_context_shared",
    "EvaluationResultSchema",
    "QueryResult",
    "StructuredAnswerSchema",
    "APIRateLimitError",
    "ValidationFailedError",
    "clean_markdown_code_block",
    "safe_json_parse",
]
