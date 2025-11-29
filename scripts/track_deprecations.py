"""
Deprecation 경고 자동 추적 및 리포트 생성

Usage:
    python scripts/track_deprecations.py

This script runs pytest with all warnings enabled and generates
a markdown report categorizing deprecation warnings by source.
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


class DeprecationTracker:
    """Deprecation 경고 추적 및 분석"""

    def __init__(self) -> None:
        self.warnings: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.output_file = Path("reports/deprecation_report.md")

    def run_tests_with_warnings(self) -> str:
        """pytest를 실행하고 모든 경고 수집"""
        # Python 경고 필터를 "always"로 설정하여 모든 경고 표시
        cmd = [
            "pytest",
            "-W",
            "always",  # 모든 경고 표시
            "--tb=no",  # 트레이스백 비활성화 (빠른 실행)
            "-v",
            "--no-cov",  # 커버리지 비활성화
            "-m",
            "",  # E2E 포함 모든 테스트 마커 허용
        ]

        print("🔍 테스트 실행 중 (모든 경고 수집)...")

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        return result.stderr + result.stdout

    def parse_warnings(self, output: str) -> None:
        """pytest 출력에서 경고 파싱"""
        # DeprecationWarning 패턴 매칭
        pattern = r"(.+?):(\d+): (DeprecationWarning|PendingDeprecationWarning): (.+)"

        for match in re.finditer(pattern, output):
            file_path = match.group(1)
            line_num = match.group(2)
            warning_type = match.group(3)
            message = match.group(4)

            # 파일 경로 정규화
            if "site-packages" in file_path:
                # 외부 라이브러리
                lib_name = self._extract_library_name(file_path)
                category = f"external:{lib_name}"
            elif "src/" in file_path or "tests/" in file_path:
                # 우리 코드
                category = "internal"
            else:
                category = "unknown"

            self.warnings[category].append(
                {
                    "file": file_path,
                    "line": line_num,
                    "type": warning_type,
                    "message": message,
                }
            )

    def _extract_library_name(self, path: str) -> str:
        """site-packages에서 라이브러리 이름 추출"""
        parts = path.split("site-packages/")
        if len(parts) > 1:
            lib = parts[1].split("/")[0]
            return lib.replace("_", "-")
        return "unknown"

    def generate_report(self) -> int:
        """Markdown 리포트 생성"""
        self.output_file.parent.mkdir(exist_ok=True)

        report: list[str] = []
        report.append("# 📋 Deprecation Warnings Report\n")
        report.append(f"Generated: {Path(__file__).name}\n\n")

        # 우리 코드의 경고 (높은 우선순위)
        if "internal" in self.warnings:
            report.append("## 🔴 Internal Code Warnings (Action Required)\n")
            report.append(
                "These warnings are from our codebase and should be fixed.\n\n"
            )

            for warning in self.warnings["internal"]:
                report.append(f"- **{warning['file']}:{warning['line']}**\n")
                report.append(f"  - Type: `{warning['type']}`\n")
                report.append(f"  - Message: {warning['message']}\n\n")

        # 외부 라이브러리 경고 (낮은 우선순위)
        external_warnings = {
            k: v for k, v in self.warnings.items() if k.startswith("external:")
        }

        if external_warnings:
            report.append("## 🟡 External Library Warnings (Monitor)\n")
            report.append("These are from dependencies. Track for future updates.\n\n")

            for lib, warnings_list in sorted(external_warnings.items()):
                lib_name = lib.split(":")[1]
                report.append(f"### {lib_name} ({len(warnings_list)} warnings)\n\n")

                # 같은 메시지는 그룹화
                unique_messages: dict[str, list[dict[str, Any]]] = {}
                for w in warnings_list:
                    msg = w["message"]
                    if msg not in unique_messages:
                        unique_messages[msg] = []
                    unique_messages[msg].append(w)

                for msg, occurrences in unique_messages.items():
                    report.append(f"- **{msg}**\n")
                    report.append(f"  - Count: {len(occurrences)}\n")
                    report.append(
                        f"  - Example: {occurrences[0]['file']}:{occurrences[0]['line']}\n\n"
                    )

        # 요약
        total = sum(len(v) for v in self.warnings.values())
        internal_count = len(self.warnings.get("internal", []))
        external_count = total - internal_count

        report.append("## 📊 Summary\n\n")
        report.append(f"- **Total Warnings**: {total}\n")
        report.append(f"- **Internal Code**: {internal_count} ⚠️\n")
        report.append(f"- **External Libraries**: {external_count}\n")

        report_text = "".join(report)
        self.output_file.write_text(report_text)

        print(f"✅ Report generated: {self.output_file}")
        print(f"   Total: {total} warnings")
        print(f"   Internal: {internal_count} (fix these!)")
        print(f"   External: {external_count} (monitor)")

        return internal_count


def main() -> None:
    """메인 실행"""
    tracker = DeprecationTracker()

    # 테스트 실행 및 경고 수집
    output = tracker.run_tests_with_warnings()

    # 경고 파싱
    tracker.parse_warnings(output)

    # 리포트 생성
    internal_count = tracker.generate_report()

    # CI에서 실패 처리 (internal 경고 있으면)
    if internal_count > 0:
        print(f"\n❌ {internal_count} internal deprecation warnings found!")
        print("   Fix these before pushing to main.")
        # 로컬에서는 실패 안 시킴 (CI에서만)
        # import sys
        # sys.exit(1)


if __name__ == "__main__":
    main()
