"""
External library type stub availability checker.

Checks which dependencies have type stubs available on PyPI
and generates installation commands for available stubs.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TypedDict


class StubCheckResult(TypedDict):
    """Result of checking a package's type stub availability."""

    package: str
    stub_package: str
    status: str  # "available" | "unavailable" | "builtin"


def get_dependencies() -> set[str]:
    """Get list of dependencies that may need type stubs."""
    return {
        "google-generativeai",
        "faststream",
        "redis",
        "jinja2",
        "tenacity",
        "python-json-logger",
        "langchain",
        "pillow",
        "aiolimiter",
        "aiofiles",
    }


def check_stub_availability(package: str) -> StubCheckResult:
    """
    Check if a type stub package exists on PyPI.

    Args:
        package: Name of the package to check

    Returns:
        Dictionary with package info and availability status
    """
    # Some packages have their own types built-in
    builtin_typed_packages = {
        "pydantic",
        "rich",
        "faststream",
        "pydantic-settings",
    }

    if package in builtin_typed_packages:
        return {
            "package": package,
            "stub_package": f"types-{package}",
            "status": "builtin",
        }

    stub_name = f"types-{package}"

    # Use pip index to check if package exists
    result = subprocess.run(
        [sys.executable, "-m", "pip", "index", "versions", stub_name],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return {
            "package": package,
            "stub_package": stub_name,
            "status": "available",
        }
    return {
        "package": package,
        "stub_package": stub_name,
        "status": "unavailable",
    }


def generate_install_commands(results: list[StubCheckResult]) -> str:
    """Generate pip install commands for available stubs."""
    available = [r["stub_package"] for r in results if r["status"] == "available"]

    if not available:
        return "# No additional type stubs available for installation"

    install_cmd = f"pip install {' '.join(available)}"

    pyproject_entries = "\n".join(f'    "{pkg}>=1.0.0",' for pkg in available)

    return f"""
# Install type stubs:
{install_cmd}

# Add to pyproject.toml [project.optional-dependencies] dev:
{pyproject_entries}
"""


def main() -> None:
    """Main entry point for the stub checker."""
    deps = get_dependencies()
    results = [check_stub_availability(pkg) for pkg in sorted(deps)]

    print("📦 Type Stub Availability Report")
    print("=" * 60)

    for r in results:
        status_icon = {
            "available": "✅",
            "unavailable": "❌",
            "builtin": "✓",
        }[r["status"]]

        print(f"{status_icon} {r['package']}: {r['stub_package']}")

    print("\n" + generate_install_commands(results))


if __name__ == "__main__":
    main()
