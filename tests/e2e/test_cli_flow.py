"""E2E: subprocess-based CLI smoke test."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_cli_non_interactive_creates_output(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project_root"
    project_root.mkdir(parents=True, exist_ok=True)

    # Minimal runtime filesystem layout for AppConfig(PROJECT_ROOT=...)
    shutil.copytree(repo_root / "templates", project_root / "templates")
    input_dir = project_root / "data" / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    (input_dir / "input_ocr.txt").write_text("테스트 OCR 텍스트", encoding="utf-8")
    (input_dir / "input_candidates.json").write_text(
        json.dumps(
            {"A": "답변 A", "B": "답변 B", "C": "답변 C"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # CLI expects an env-style config file; extension is not important.
    config_path = project_root / "test_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "GEMINI_API_KEY=" + ("AIza" + ("0" * 35)),
                "GEMINI_MODEL_NAME=gemini-flash-latest",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(project_root),
            "GEMINI_API_KEY": "AIza" + ("0" * 35),
            # E2E flags: deterministic and no network calls.
            "SQ_E2E": "1",
            "SQ_DISABLE_CONTEXT_CACHE": "1",
        }
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "--non-interactive",
            "--config",
            str(config_path),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"

    output_dir = project_root / "data" / "outputs"
    outputs = list(output_dir.glob("result_turn_*.md"))
    assert outputs, (
        f"결과 파일이 생성되지 않았습니다.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )
