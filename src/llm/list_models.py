# mypy: disable-error-code=attr-defined
"""Gemini Model Listing Utility module.

CLI script to list available Gemini models that support generateContent.
Useful for verifying API key validity and discovering model names.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("No API key found in .env (GEMINI_API_KEY)")
    sys.exit(1)

client = genai.Client(api_key=api_key)

logger.info("Listing models for configured Gemini key...")
try:
    # google-genai SDK 에서는 client.models.list() 사용
    for m in client.models.list():
        # supported_generation_methods 속성이 다른 이름이거나 없을 수 있음
        # 기본적으로 models.list()는 사용 가능한 모델을 반환
        logger.info(m.name)
except Exception as e:  # noqa: BLE001
    logger.error("Error listing models: %s", e)
