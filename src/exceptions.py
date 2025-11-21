class APIRateLimitError(Exception):
    """Raised when API rate limit is exceeded."""


class ValidationFailedError(Exception):
    """Raised when data validation fails."""


class CacheCreationError(Exception):
    """Raised when context cache creation fails."""


class SafetyFilterError(Exception):
    """Raised when generation is blocked by safety filters or non-STOP finish reasons."""
