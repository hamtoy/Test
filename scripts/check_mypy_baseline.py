"""
mypy 베이스라인 측정 스크립트
"""

import datetime
import re
import subprocess


def run_mypy() -> str:
    """mypy 실행 및 출력 캡처"""
    result = subprocess.run(
        ["mypy", "src/", "--config-file", "pyproject.toml"],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def parse_errors(output: str) -> dict[str, list[str]]:
    """
    에러를 파일별로 분류

    Returns:
        {
            "src/agent/core.py": [
                "Line 45: error: Function is missing a return type annotation",
                "Line 67: error: Need type annotation for 'items'"
            ],
            ...
        }
    """
    errors_by_file: dict[str, list[str]] = {}

    for line in output.split("\n"):
        # src/agent/core.py:45: error: ...
        match = re.match(r"^(src/[^:]+):(\d+):\s*error:\s*(.+)$", line)
        if match:
            filepath, line_num, error_msg = match.groups()
            full_error = f"Line {line_num}: {error_msg}"
            errors_by_file.setdefault(filepath, []).append(full_error)

    return errors_by_file


def categorize_errors(errors: dict[str, list[str]]) -> dict[str, int]:
    """
    에러를 카테고리별로 집계

    Returns:
        {
            "missing-return-type": 45,
            "need-type-annotation": 32,
            "arg-type": 12,
            ...
        }
    """
    categories: dict[str, int] = {}

    patterns = {
        "missing-return-type": r"missing a return type",
        "need-type-annotation": r"Need type annotation",
        "arg-type": r"Argument .* has incompatible type",
        "return-value": r"Incompatible return value type",
        "no-untyped-def": r"Function is missing a type annotation",
    }

    for error_list in errors.values():
        for error in error_list:
            for category, pattern in patterns.items():
                if re.search(pattern, error, re.IGNORECASE):
                    categories[category] = categories.get(category, 0) + 1
                    break

    return categories


def generate_report(
    errors_by_file: dict[str, list[str]],
    categories: dict[str, int],
) -> None:
    """HTML 리포트 생성"""

    total_errors = sum(len(errs) for errs in errors_by_file.values())
    total_files = len(errors_by_file)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>mypy Baseline Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 40px; }}
        .summary {{ background: #f0f0f0; padding: 20px; border-radius: 8px; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #e53e3e; }}
        .metric-label {{ color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f7fafc; }}
    </style>
</head>
<body>
    <h1>mypy Baseline Report - Level 0.5</h1>
    <p>Generated: {timestamp}</p>

    <div class="summary">
        <div class="metric">
            <div class="metric-value">{total_errors}</div>
            <div class="metric-label">Total Errors</div>
        </div>
        <div class="metric">
            <div class="metric-value">{total_files}</div>
            <div class="metric-label">Files with Errors</div>
        </div>
    </div>

    <h2>Error Categories</h2>
    <table>
        <thead>
            <tr><th>Category</th><th>Count</th></tr>
        </thead>
        <tbody>
"""

    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        html += f"<tr><td>{category}</td><td>{count}</td></tr>\n"

    html += """        </tbody>
    </table>

    <h2>Files with Most Errors (Top 20)</h2>
    <table>
        <thead>
            <tr><th>File</th><th>Error Count</th></tr>
        </thead>
        <tbody>
"""

    top_files = sorted(errors_by_file.items(), key=lambda x: len(x[1]), reverse=True)[
        :20
    ]
    for filepath, errors in top_files:
        html += f"<tr><td><code>{filepath}</code></td><td>{len(errors)}</td></tr>\n"

    html += """        </tbody>
    </table>
</body>
</html>
"""

    with open("mypy_baseline_report.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'=' * 70}")
    print("📊 mypy Baseline Summary")
    print(f"{'=' * 70}")
    print(f"Total errors: {total_errors}")
    print(f"Files affected: {total_files}")
    print("Report: mypy_baseline_report.html")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    print("Running mypy baseline check...")
    output = run_mypy()
    errors_by_file = parse_errors(output)
    categories = categorize_errors(errors_by_file)
    generate_report(errors_by_file, categories)
