# mypy: disable-error-code=attr-defined
"""Gemini Model Listing Utility module.

CLI script to list available Gemini models that support generateContent.
Useful for verifying API key validity and discovering model names.
"""

import logging
import os
import sys

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("No API key found in .env (GEMINI_API_KEY)")
    sys.exit(1)

genai.configure(api_key=api_key)

logger.info("Listing models for configured Gemini key...")
try:
    for model in genai.list_models():
        methods = getattr(model, "supported_generation_methods", [])
        if "generateContent" in methods:
            logger.info(model.name)
except Exception as e:  # noqa: BLE001
    logger.error("Error listing models: %s", e)
