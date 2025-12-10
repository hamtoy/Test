"""
Render a Jinja2 template with JSON context.

Usage:
  uv run python scripts/render_prompt.py \
    --template system/qa/explanation.j2 \
    --context examples/sample_image_meta.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def build_env(root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(root / "templates")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(template_path: str, context: dict, root: Path) -> str:
    env = build_env(root)
    tpl = env.get_template(template_path)
    return tpl.render(**context)


def main() -> None:
    # scripts/dev is nested one level; go two levels up to reach repo root
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description="Render a Jinja2 prompt template.")
    parser.add_argument(
        "--template",
        default="system/qa/explanation.j2",
        help="Template path relative to templates/ (e.g., system/qa/explanation.j2)",
    )
    parser.add_argument(
        "--context",
        default=str(repo_root / "examples" / "sample_image_meta.json"),
        help="Path to JSON context file",
    )
    args = parser.parse_args()

    context_path = Path(args.context)
    if not context_path.exists():
        raise FileNotFoundError(f"Context file not found: {context_path}")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    output = render(args.template, context, repo_root)
    print(output)


if __name__ == "__main__":
    main()
