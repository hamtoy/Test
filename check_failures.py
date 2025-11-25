import subprocess

result = subprocess.run(
    ["uv", "run", "pytest", "tests/test_agent.py", "-v", "--tb=short"],
    capture_output=True,
    text=True,
)

print(result.stdout)
print(result.stderr)

# Extract failed tests
for line in result.stdout.split("\n"):
    if "FAILED" in line:
        print(f"\n>>> {line}")
