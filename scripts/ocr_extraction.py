import json
import os
import time
from pathlib import Path
from typing import Iterable, List, Tuple

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

MODEL_NAME = (
    "gemini-3-pro-preview"  # Use flash for speed/cost efficiency on many images
)
EXPORT_DIRS = [Path("export1"), Path("export2")]
OUTPUT_FILE = Path("data/inputs/notion_sample_ocr.txt")
OUTPUT_JSONL = Path("data/inputs/notion_sample_ocr.jsonl")
OCR_PROMPT = """
당신은 한국어 문서 OCR 전문가입니다. 
이 이미지에서 텍스트를 추출해주세요.

규칙:
1. 모든 한국어 텍스트를 정확하게 추출
2. 문단 구조와 줄바꿈을 유지
3. 표나 레이아웃이 있다면 구조를 보존
4. 특수문자, 숫자, 영문도 정확히 추출
5. 이미지에 없는 내용은 추가하지 마세요

출력 형식: 원본 문서의 레이아웃을 최대한 유지하여 텍스트만 출력
"""
OCR_PROMPT_LAYOUT = """
이 이미지는 금융/경제 뉴스 문서입니다. 
다단 레이아웃을 인식하고 각 섹션을 순서대로 추출하세요. 

추출 순서:
1. 제목/헤더
2. 본문 (왼쪽에서 오른쪽, 위에서 아래 순서)
3. 부가 정보/표

각 섹션은 빈 줄로 구분해주세요.
"""
MAX_RETRIES = 1
PREPROCESS_MAX_DIM = (2048, 2048)
BINARY_THRESHOLD = 180
MIN_RESOLUTION = 1000  # Upscale images smaller than this
CONTRAST_ENHANCEMENT_FACTOR = 1.3  # Improves text recognition


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
    grayscale: bool = False,
    binarize: bool = False,
    threshold: int = BINARY_THRESHOLD,
) -> Image.Image:
    from PIL import ImageEnhance, ImageOps

    working = ImageOps.exif_transpose(img) or img

    # Upscale low-resolution images
    width, height = working.size
    if width < MIN_RESOLUTION or height < MIN_RESOLUTION:
        scale_factor = max(MIN_RESOLUTION / width, MIN_RESOLUTION / height)
        new_size = (int(width * scale_factor), int(height * scale_factor))
        working = working.resize(new_size, Image.Resampling.LANCZOS)

    # Apply contrast enhancement
    enhancer = ImageEnhance.Contrast(working)
    working = enhancer.enhance(CONTRAST_ENHANCEMENT_FACTOR)

    # Resize if needed
    if max_dim:
        working.thumbnail(max_dim, Image.Resampling.LANCZOS)

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
    use_layout_prompt: bool = False,
) -> Tuple[str, str | None]:
    last_error: str | None = None
    prompt = OCR_PROMPT_LAYOUT if use_layout_prompt else OCR_PROMPT
    for attempt in range(1, max_retries + 2):
        with Image.open(img_path) as img:
            prepared = _preprocess_image(img.copy()) if preprocess else img.copy()
        try:
            response = model.generate_content([prompt, prepared])
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
    use_layout_prompt: bool = True,
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
                model,
                img_path,
                preprocess=preprocess,
                max_retries=max_retries,
                use_layout_prompt=use_layout_prompt,
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
