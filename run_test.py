"""Run pytest and save results to file."""

import subprocess
import sys

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_deprecation_warnings.py::TestDeprecationWarnings",
        "-v",
        "--tb=short",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
)

with open("pytest_output.txt", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nReturn code: {result.returncode}\n")

print("Results saved to pytest_output.txt")
print(f"Return code: {result.returncode}")

# Print summary
lines = result.stdout.split("\n")
for line in lines:
    if "PASSED" in line or "FAILED" in line:
        print(line)
