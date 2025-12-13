#!/usr/bin/env python3
"""Unified build release script for shining-quasar.

This script handles both frontend building and backend preparation
to simplify the release process.

Usage:
    python scripts/build_release.py [--verbose] [--skip-frontend] [--skip-backend]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


class BuildError(Exception):
    """Raised when a build step fails."""


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[1]


def run_command(
    cmd: list[str],
    cwd: Path,
    verbose: bool = False,
    description: str = "",
) -> subprocess.CompletedProcess[str]:
    """Run a command and handle output.

    Args:
        cmd: Command and arguments to run
        cwd: Working directory
        verbose: Whether to show command output
        description: Description of the step

    Returns:
        CompletedProcess result

    Raises:
        BuildError: If command fails
    """
    if description:
        print(f"  → {description}...")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=not verbose,
            text=True,
            check=True,
        )
        if verbose and result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise BuildError(f"Command failed: {' '.join(cmd)}\n{error_msg}") from e


def build_frontend(repo_root: Path, verbose: bool = False) -> None:
    """Build the frontend using npm/pnpm.

    Args:
        repo_root: Repository root directory
        verbose: Whether to show build output
    """
    print("\n📦 Building Frontend...")

    # Check for package manager
    if shutil.which("pnpm"):
        pkg_manager = "pnpm"
    elif shutil.which("npm"):
        pkg_manager = "npm"
    else:
        raise BuildError(
            "Neither pnpm nor npm found. Please install a package manager."
        )

    # Install dependencies
    run_command(
        [pkg_manager, "install"],
        cwd=repo_root,
        verbose=verbose,
        description="Installing dependencies",
    )

    # Run build
    run_command(
        [pkg_manager, "run", "build"],
        cwd=repo_root,
        verbose=verbose,
        description="Building frontend assets",
    )

    # Verify dist was created
    dist_dir = repo_root / "static" / "dist"
    if not dist_dir.exists():
        raise BuildError(f"Frontend build failed: {dist_dir} not found")

    print("  ✅ Frontend build complete")


def copy_static_assets(repo_root: Path, verbose: bool = False) -> None:
    """Copy frontend build output to backend static directory.

    Args:
        repo_root: Repository root directory
        verbose: Whether to show copy operations
    """
    print("\n📁 Copying Static Assets...")

    source_dir = repo_root / "static" / "dist"
    target_dir = repo_root / "src" / "web" / "static"

    if not source_dir.exists():
        print("  ⚠️ No dist directory found, skipping asset copy")
        return

    # Create target directory if needed
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    copied_count = 0
    for item in source_dir.iterdir():
        target_path = target_dir / item.name
        if item.is_file():
            shutil.copy2(item, target_path)
            copied_count += 1
            if verbose:
                print(f"    Copied: {item.name}")
        elif item.is_dir():
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.copytree(item, target_path)
            copied_count += 1
            if verbose:
                print(f"    Copied directory: {item.name}/")

    print(f"  ✅ Copied {copied_count} items to {target_dir.relative_to(repo_root)}")


def verify_backend(repo_root: Path, verbose: bool = False) -> None:
    """Verify backend can be imported and run.

    Args:
        repo_root: Repository root directory
        verbose: Whether to show verification output
    """
    print("\n🔍 Verifying Backend...")

    # Check Python import
    run_command(
        [sys.executable, "-c", "import src; print(f'Version: {src.__version__}')"],
        cwd=repo_root,
        verbose=verbose,
        description="Checking module import",
    )

    # Run basic syntax check
    run_command(
        [sys.executable, "-m", "py_compile", "src/__init__.py"],
        cwd=repo_root,
        verbose=verbose,
        description="Syntax verification",
    )

    print("  ✅ Backend verification complete")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Build and package shining-quasar for release"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed build output",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip frontend build step",
    )
    parser.add_argument(
        "--skip-backend",
        action="store_true",
        help="Skip backend verification step",
    )

    args = parser.parse_args()
    repo_root = get_repo_root()

    print("=" * 60)
    print("🚀 shining-quasar Release Build")
    print("=" * 60)
    print(f"Repository: {repo_root}")

    try:
        if not args.skip_frontend:
            build_frontend(repo_root, verbose=args.verbose)
            copy_static_assets(repo_root, verbose=args.verbose)
        else:
            print("\n⏭️ Skipping frontend build")

        if not args.skip_backend:
            verify_backend(repo_root, verbose=args.verbose)
        else:
            print("\n⏭️ Skipping backend verification")

        print("\n" + "=" * 60)
        print("✅ BUILD SUCCESSFUL")
        print("=" * 60)
        return 0

    except BuildError as e:
        print(f"\n❌ BUILD FAILED: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⚠️ Build interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
