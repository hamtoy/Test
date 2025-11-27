#!/usr/bin/env python3
"""
v2.5 → v3.0 Interactive Migration Wizard.

This tool helps migrate from shining-quasar v2.5 to v3.0.
It provides a step-by-step guide for the migration process.

Usage:
    python scripts/interactive_migration_wizard.py

Exit Codes:
    0: Migration completed successfully
    1: Migration failed or cancelled
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Tuple


def print_banner() -> None:
    """Print the migration wizard banner."""
    print(
        """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║    🚀 shining-quasar v3.0 Migration Wizard                    ║
║                                                                ║
║    This tool will help you migrate from v2.5 to v3.0.         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    )


def print_step(step_num: int, total: int, title: str) -> None:
    """Print a step header."""
    print(f"\n{'─' * 60}")
    print(f"  Step {step_num}/{total}: {title}")
    print(f"{'─' * 60}")


def ask_continue(prompt: str = "Continue?") -> bool:
    """Ask the user if they want to continue.

    Args:
        prompt: The prompt to display

    Returns:
        True if user wants to continue, False otherwise
    """
    response = input(f"\n{prompt} (y/N): ").strip().lower()
    return response in ("y", "yes")


def run_command(
    cmd: List[str], description: str, capture_output: bool = False
) -> Tuple[bool, str]:
    """Run a shell command.

    Args:
        cmd: Command and arguments
        description: Description of what the command does
        capture_output: Whether to capture stdout/stderr

    Returns:
        Tuple of (success, output)
    """
    print(f"  → Running: {' '.join(cmd)}")

    try:
        if capture_output:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        else:
            result_bytes = subprocess.run(cmd, check=False)
            return result_bytes.returncode == 0, ""
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def step_welcome() -> bool:
    """Step 0: Welcome and overview."""
    print(
        """
This wizard will guide you through the following steps:

  📋 Step 1: Verify readiness
     Check for deprecated imports and v3.0 compatibility

  💾 Step 2: Backup current code
     Create a git stash to preserve current state

  🔧 Step 3: Run automated migration
     Apply import path migrations automatically

  ✅ Step 4: Test & validate
     Run tests to ensure everything works

  📖 Step 5: Review changes
     View what was changed and next steps
"""
    )

    return ask_continue("Ready to start?")


def step_verify_readiness() -> bool:
    """Step 1: Verify readiness."""
    print("\n🔍 Checking for deprecated imports and v3.0 compatibility...")

    # Check if verify_v3_readiness.py exists
    script_path = Path("scripts/verify_v3_readiness.py")
    if not script_path.exists():
        print("  ❌ scripts/verify_v3_readiness.py not found")
        return False

    success, output = run_command(
        [sys.executable, str(script_path)],
        "Check v3.0 readiness",
        capture_output=True,
    )

    print(output)

    if success:
        print("\n  ✅ Ready for migration!")
        return True
    else:
        print("\n  ⚠️  Some issues were found.")
        return ask_continue("Continue anyway?")


def step_backup() -> bool:
    """Step 2: Create backup."""
    print("\n💾 Creating backup of current state...")

    # Check if there are uncommitted changes
    success, output = run_command(
        ["git", "status", "--porcelain"],
        "Check git status",
        capture_output=True,
    )

    if output.strip():
        print("  📝 Uncommitted changes detected:")
        for line in output.strip().split("\n")[:5]:
            print(f"      {line}")
        if len(output.strip().split("\n")) > 5:
            print("      ...")

        if ask_continue("Create git stash 'pre-v3-migration'?"):
            success, _ = run_command(
                ["git", "stash", "push", "-m", "pre-v3-migration"],
                "Create git stash",
            )
            if success:
                print("  ✅ Stash created: pre-v3-migration")
            else:
                print("  ❌ Failed to create stash")
                return False
    else:
        print("  ✅ Working directory is clean")

    return True


def step_migrate() -> bool:
    """Step 3: Run automated migration."""
    print("\n🔧 Running automated migration...")

    # Check if migrate_imports.py exists
    script_path = Path("scripts/migrate_imports.py")
    if not script_path.exists():
        print("  ❌ scripts/migrate_imports.py not found")
        return False

    # First do a dry run
    print("\n  📋 Checking what would be changed (dry run)...")
    success, output = run_command(
        [sys.executable, str(script_path), "--check", "--path", "."],
        "Check migrations",
        capture_output=True,
    )
    print(output)

    if "No deprecated imports found" in output:
        print("  ✅ No migrations needed!")
        return True

    if ask_continue("Apply these changes?"):
        success, output = run_command(
            [sys.executable, str(script_path), "--fix", "--path", "."],
            "Apply migrations",
            capture_output=True,
        )
        print(output)

        if success:
            print("  ✅ Migrations applied successfully!")
            return True
        else:
            print("  ❌ Migration failed")
            return False

    return True


def step_test() -> bool:
    """Step 4: Run tests."""
    print("\n✅ Running tests to validate migration...")

    # First verify imports work
    print("\n  📦 Testing v3.0 imports...")
    success, output = run_command(
        [
            sys.executable,
            "-c",
            """
from src import __version__, GeminiAgent, AppConfig
from src import WorkflowResult, EvaluationResultSchema, QueryResult
from src import BudgetExceededError, APIRateLimitError, ValidationFailedError
print(f"  ✅ v3.0 imports successful (version: {__version__})")
""",
        ],
        "Test imports",
        capture_output=True,
    )

    if success:
        print(output.strip())
    else:
        print(f"  ❌ Import test failed: {output}")
        return False

    # Ask about running full test suite
    if ask_continue("Run full test suite? (may take a few minutes)"):
        print("\n  🧪 Running pytest...")
        success, _ = run_command(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            "Run pytest",
        )

        if success:
            print("  ✅ All tests passed!")
        else:
            print("  ⚠️  Some tests failed")
            return ask_continue("Continue anyway?")

    return True


def step_review() -> bool:
    """Step 5: Review changes and next steps."""
    print("\n📖 Migration Summary")
    print("=" * 60)

    print(
        """
✅ Migration Complete!

What was done:
  • Verified v3.0 compatibility
  • Applied import path migrations (if any)
  • Validated v3.0 public API imports

Next Steps:
  1. Review the changes: git diff
  2. Run your application to verify functionality
  3. Commit the changes: git add . && git commit -m "Migrate to v3.0"
  4. Update any documentation or CI/CD pipelines

Key Changes in v3.0:
  • New public API in src/__init__.py
  • Deprecated imports emit warnings (will be removed in v4.0)
  • Python 3.10+ required
  • Mypy strict mode on core modules

For more details, see:
  • docs/BREAKING_CHANGES_v3.md
  • docs/ARCHITECTURE.md

If you need to rollback:
  git stash pop  # Restore pre-migration stash
"""
    )

    return True


def main() -> int:
    """Main entry point for the migration wizard.

    Returns:
        0 on success, 1 on failure
    """
    print_banner()

    steps: List[Tuple[str, Callable[[], bool]]] = [
        ("Welcome", step_welcome),
        ("Verify Readiness", step_verify_readiness),
        ("Backup", step_backup),
        ("Migrate", step_migrate),
        ("Test & Validate", step_test),
        ("Review", step_review),
    ]

    for i, (title, step_func) in enumerate(steps):
        if i > 0:  # Skip step header for welcome
            print_step(i, len(steps) - 1, title)

        try:
            if not step_func():
                print(f"\n❌ Migration aborted at step: {title}")
                print("  To retry, run this wizard again.")
                return 1
        except KeyboardInterrupt:
            print("\n\n⚠️  Migration cancelled by user")
            return 1
        except Exception as e:
            print(f"\n❌ Error during {title}: {e}")
            return 1

    print("\n🎉 Migration wizard complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
