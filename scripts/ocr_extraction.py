import json
import os
import time
from pathlib import Path
from typing import Iterable, List, Tuple

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

MODEL_NAME = (
    "gemini-3-pro-preview"  # Use flash for speed/cost efficiency on many images
)
EXPORT_DIRS = [Path("export1"), Path("export2")]
OUTPUT_FILE = Path("data/inputs/notion_sample_ocr.txt")
OUTPUT_JSONL = Path("data/inputs/notion_sample_ocr.jsonl")
OCR_PROMPT = (
    "Extract all text from this image exactly as it appears. "
    "Do not add any conversational filler."
)
MAX_RETRIES = 1
PREPROCESS_MAX_DIM = (1600, 1600)
BINARY_THRESHOLD = 180


def _iter_images(paths: Iterable[Path]) -> List[Path]:
    exts = ("*.png", "*.jpg", "*.jpeg")
    images: List[Path] = []
    for base in paths:
        for ext in exts:
            images.extend(base.rglob(ext))
    return images


def _write_header(output_file: Path, jsonl_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    for path in (output_file, jsonl_file):
        path.write_text("", encoding="utf-8")
    with open(output_file, "w", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"OCR Extraction Results - {timestamp}\n")
        f.write("=" * 50 + "\n\n")


def _preprocess_image(
    img: Image.Image,
    max_dim: Tuple[int, int] = PREPROCESS_MAX_DIM,
    grayscale: bool = True,
    binarize: bool = True,
    threshold: int = BINARY_THRESHOLD,
) -> Image.Image:
    working = ImageOps.exif_transpose(img) or img
    if max_dim:
        working.thumbnail(max_dim)
    if grayscale:
        working = ImageOps.grayscale(working)
    if binarize:
        working = working.point(lambda p: 255 if p > threshold else 0)
    return working


def _extract_with_retries(
    model: "genai.GenerativeModel",  # type: ignore[name-defined]
    img_path: Path,
    preprocess: bool = True,
    max_retries: int = MAX_RETRIES,
) -> Tuple[str, str | None]:
    last_error: str | None = None
    for attempt in range(1, max_retries + 2):
        with Image.open(img_path) as img:
            prepared = _preprocess_image(img.copy()) if preprocess else img.copy()
        try:
            response = model.generate_content([OCR_PROMPT, prepared])
            text = (response.text or "").strip()
            return text, None
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
        if attempt <= max_retries:
            time.sleep(1)
            continue
        return "", last_error
    return "", last_error


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def extract_text_from_images(
    export_dirs: Iterable[Path] = EXPORT_DIRS,
    output_file: Path = OUTPUT_FILE,
    jsonl_file: Path = OUTPUT_JSONL,
    model_name: str = MODEL_NAME,
    preprocess: bool = True,
    max_retries: int = MAX_RETRIES,
) -> None:
    """Extract text from images in given directories and write to a text + JSONL file."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    genai.configure(api_key=api_key)  # type: ignore[attr-defined]
    model = genai.GenerativeModel(model_name)  # type: ignore[attr-defined]

    _write_header(output_file, jsonl_file)

    total_images = 0
    processed_images = 0

    dir_names = ", ".join(str(d) for d in export_dirs)
    print(f"Starting OCR extraction from: {dir_names}")
    print(f"Output file: {output_file}\nJSONL log: {jsonl_file}\n")

    for dir_path in export_dirs:
        if not dir_path.exists():
            print(f"Directory not found: {dir_path}")
            continue

        images = _iter_images([dir_path])
        total_images += len(images)

        for img_path in images:
            print(f"Processing: {img_path}")
            text, error = _extract_with_retries(
                model, img_path, preprocess=preprocess, max_retries=max_retries
            )

            if error:
                print(f"Failed to process {img_path}: {error}")
            else:
                processed_images += 1

            print("-" * 20)
            print(f"Extracted Text ({img_path.name}):")
            print(text)
            print("-" * 20 + "\n")

            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"### File: {img_path}\n")
                f.write(text + ("\n\n" if text else "\n"))
                f.write("-" * 30 + "\n\n")

            _append_jsonl(
                jsonl_file,
                {
                    "file": str(img_path),
                    "text": text,
                    "error": error,
                },
            )

            time.sleep(1)  # Rate limit precaution

    print(f"\nExtraction complete. Processed {processed_images}/{total_images} images.")
    print(f"Results saved to {output_file} (JSONL: {jsonl_file})")


if __name__ == "__main__":
    extract_text_from_images()
