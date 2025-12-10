# mypy: disable-error-code=attr-defined
import logging
import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv

from src.llm.init_genai import configure_genai  # noqa: E402

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("No API key found in .env (GEMINI_API_KEY)")
    sys.exit(1)

configure_genai(api_key)

logger.info("Listing models for configured Gemini key...")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            logger.info(m.name)
except Exception as e:  # noqa: BLE001
    logger.error("Error listing models: %s", e)
