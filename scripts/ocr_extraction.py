import os
import time
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

load_dotenv()


def extract_text_from_images():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-3-pro-preview"
    )  # Use flash for speed/cost efficiency on many images

    export_dirs = ["export1", "export2"]
    output_file = Path("data/inputs/notion_sample_ocr.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Clear existing file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"OCR Extraction Results - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")

    total_images = 0
    processed_images = 0

    print(f"Starting OCR extraction from: {', '.join(export_dirs)}")
    print(f"Output file: {output_file}\n")

    for dir_name in export_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"Directory not found: {dir_name}")
            continue

        images = (
            list(dir_path.rglob("*.png"))
            + list(dir_path.rglob("*.jpg"))
            + list(dir_path.rglob("*.jpeg"))
        )
        total_images += len(images)

        for img_path in images:
            print(f"Processing: {img_path}")
            try:
                img = Image.open(img_path)
                response = model.generate_content(
                    [
                        "Extract all text from this image exactly as it appears. Do not add any conversational filler.",
                        img,
                    ]
                )
                text = response.text.strip()

                # Print to console as requested
                print("-" * 20)
                print(f"Extracted Text ({img_path.name}):")
                print(text)
                print("-" * 20 + "\n")

                # Save to file
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"### File: {img_path}\n")
                    f.write(text + "\n\n")
                    f.write("-" * 30 + "\n\n")

                processed_images += 1
                time.sleep(1)  # Rate limit precaution

            except Exception as e:
                print(f"Failed to process {img_path}: {e}")

    print(f"\nExtraction complete. Processed {processed_images}/{total_images} images.")
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    extract_text_from_images()
