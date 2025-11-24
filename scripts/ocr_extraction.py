import os
import time
from pathlib import Path
from typing import Iterable, List

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

MODEL_NAME = (
    "gemini-3-pro-preview"  # Use flash for speed/cost efficiency on many images
)
EXPORT_DIRS = [Path("export1"), Path("export2")]
OUTPUT_FILE = Path("data/inputs/notion_sample_ocr.txt")
OCR_PROMPT = (
    "Extract all text from this image exactly as it appears. "
    "Do not add any conversational filler."
)


def _iter_images(paths: Iterable[Path]) -> List[Path]:
    exts = ("*.png", "*.jpg", "*.jpeg")
    images: List[Path] = []
    for base in paths:
        for ext in exts:
            images.extend(base.rglob(ext))
    return images


def _write_header(output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"OCR Extraction Results - {timestamp}\n")
        f.write("=" * 50 + "\n\n")


def extract_text_from_images(
    export_dirs: Iterable[Path] = EXPORT_DIRS,
    output_file: Path = OUTPUT_FILE,
    model_name: str = MODEL_NAME,
) -> None:
    """Extract text from images in given directories and write to a single file."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    _write_header(output_file)

    total_images = 0
    processed_images = 0

    dir_names = ", ".join(str(d) for d in export_dirs)
    print(f"Starting OCR extraction from: {dir_names}")
    print(f"Output file: {output_file}\n")

    for dir_path in export_dirs:
        if not dir_path.exists():
            print(f"Directory not found: {dir_path}")
            continue

        images = _iter_images([dir_path])
        total_images += len(images)

        for img_path in images:
            print(f"Processing: {img_path}")
            try:
                with Image.open(img_path) as img:
                    response = model.generate_content([OCR_PROMPT, img])
                text = (response.text or "").strip()

                print("-" * 20)
                print(f"Extracted Text ({img_path.name}):")
                print(text)
                print("-" * 20 + "\n")

                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"### File: {img_path}\n")
                    f.write(text + "\n\n")
                    f.write("-" * 30 + "\n\n")

                processed_images += 1
                time.sleep(1)  # Rate limit precaution

            except Exception as e:  # noqa: BLE001
                print(f"Failed to process {img_path}: {e}")

    print(f"\nExtraction complete. Processed {processed_images}/{total_images} images.")
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    extract_text_from_images()
