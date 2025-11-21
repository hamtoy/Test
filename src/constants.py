"""
Shared constants for pricing and sensitive-data handling.
"""

from typing import Final, List, Optional, TypedDict


class PricingTier(TypedDict):
    max_input_tokens: Optional[int]
    input_rate: float
    output_rate: float


# Pricing per 1M tokens (USD) for Gemini models.
# Ordered tiers: first match wins.
PRICING_TIERS: Final[dict[str, List[PricingTier]]] = {
    "gemini-3-pro-preview": [
        {"max_input_tokens": 200_000, "input_rate": 2.00, "output_rate": 12.00},
        {"max_input_tokens": None, "input_rate": 4.00, "output_rate": 18.00},
    ],
}

# Pattern for masking sensitive API keys in logs (e.g., Google API keys).
SENSITIVE_PATTERN: Final[str] = r"AIza[0-9A-Za-z_-]{35}"
