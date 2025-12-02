"""Type wrappers for google-generativeai library.

Since google-generativeai lacks complete type stubs, we provide
typed wrappers for commonly used functions. These wrappers provide
type safety while the underlying library remains untyped.

Usage:
    from src.llm.gemini_types import (
        configure_genai,
        create_generative_model,
        GenerationConfig,
    )

    configure_genai(api_key="your-key")
    model = create_generative_model("gemini-1.5-pro")
"""

# mypy: disable-error-code=attr-defined
from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict

import google.generativeai as genai


class GenerationConfig(TypedDict, total=False):
    """Generation configuration for Gemini API."""

    temperature: float
    top_p: float
    top_k: int
    max_output_tokens: int
    candidate_count: int
    stop_sequences: list[str]


class SafetySettings(TypedDict, total=False):
    """Safety settings for content generation."""

    category: str
    threshold: str


class GenerateContentResponse:
    """Data class representing the structure of a Gemini API response.

    This is not a protocol but a reference class showing the expected
    response structure. Actual responses from the API will be typed as Any.
    """

    text: str
    candidates: list[Any]
    prompt_feedback: dict[str, Any]


# Type-safe wrapper functions


def configure_genai(api_key: str) -> None:
    """Configure the google-generativeai library with an API key.

    This is a typed wrapper for genai.configure().

    Args:
        api_key: The Gemini API key
    """
    genai.configure(api_key=api_key)


def create_generative_model(
    model_name: str,
    generation_config: Optional[GenerationConfig] = None,
    safety_settings: Optional[list[SafetySettings]] = None,
) -> Any:
    """Create a GenerativeModel instance.

    This is a typed wrapper for genai.GenerativeModel().

    Args:
        model_name: Name of the model (e.g., "gemini-1.5-pro")
        generation_config: Optional generation configuration
        safety_settings: Optional safety settings

    Returns:
        A GenerativeModel instance (typed as Any since the library lacks stubs)
    """
    kwargs: dict[str, Any] = {}
    if generation_config is not None:
        kwargs["generation_config"] = generation_config
    if safety_settings is not None:
        kwargs["safety_settings"] = safety_settings

    return genai.GenerativeModel(model_name, **kwargs)


def list_available_models() -> list[Any]:
    """List all available Gemini models.

    This is a typed wrapper for genai.list_models().

    Returns:
        List of available model objects
    """
    return list(genai.list_models())


def embed_content(
    model: str,
    content: str,
    task_type: str = "retrieval_query",
) -> dict[str, Any]:
    """Generate embeddings for content.

    This is a typed wrapper for genai.embed_content().

    Args:
        model: Model name for embeddings
        content: Text content to embed
        task_type: Type of embedding task

    Returns:
        Dictionary containing the embedding result with 'embedding' key
    """
    result: Any = genai.embed_content(model=model, content=content, task_type=task_type)
    # The result is a dict-like object with 'embedding' key
    # We convert to dict to provide a concrete return type
    if hasattr(result, "keys"):
        return dict(result)
    # Fallback: wrap in dict if result is the embedding directly
    return {"embedding": result}


__all__ = [
    "GenerationConfig",
    "SafetySettings",
    "GenerateContentResponse",
    "configure_genai",
    "create_generative_model",
    "list_available_models",
    "embed_content",
]
