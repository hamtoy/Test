"""Tests for the migrate_imports.py script."""

import tempfile
from pathlib import Path

import pytest

from scripts.migrate_imports import (
    IMPORT_MAPPINGS,
    MigrationResult,
    collect_files,
    generate_diff,
    main,
    migrate_file,
    should_exclude,
)


class TestShouldExclude:
    """Tests for the should_exclude function."""

    def test_exclude_by_filename_pattern(self):
        """Test excluding files by filename pattern."""
        filepath = Path("/path/to/test_file.py")
        assert should_exclude(filepath, ["test_*.py"]) is True

    def test_exclude_by_path_pattern(self):
        """Test excluding files by full path pattern."""
        filepath = Path("/path/to/vendor/module.py")
        assert should_exclude(filepath, ["*vendor*"]) is True

    def test_no_exclude_when_no_match(self):
        """Test that non-matching files are not excluded."""
        filepath = Path("/path/to/main.py")
        assert should_exclude(filepath, ["test_*.py", "*vendor*"]) is False

    def test_empty_exclude_patterns(self):
        """Test with empty exclude patterns."""
        filepath = Path("/path/to/file.py")
        assert should_exclude(filepath, []) is False


class TestMigrateFile:
    """Tests for the migrate_file function."""

    def test_no_changes_needed(self):
        """Test file with no deprecated imports."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("from src.config.constants import FOO\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath)
            assert result is not None
            assert result.has_changes is False
            assert len(result.changes) == 0
        finally:
            filepath.unlink()

    def test_detect_deprecated_import(self):
        """Test detection of deprecated import in check mode."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("from src.utils import some_function\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath, fix=False)
            assert result is not None
            assert result.has_changes is True
            assert len(result.changes) == 1
            # Original content should remain unchanged
            assert (
                filepath.read_text() == "from src.utils import some_function\n"
            )
        finally:
            filepath.unlink()

    def test_fix_deprecated_import(self):
        """Test fixing deprecated import."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("from src.utils import some_function\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath, fix=True)
            assert result is not None
            assert result.has_changes is True
            # Content should be updated
            assert (
                filepath.read_text()
                == "from src.infra.utils import some_function\n"
            )
        finally:
            filepath.unlink()

    def test_multiple_imports_in_file(self):
        """Test file with multiple deprecated imports."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(
                "from src.utils import helper\n"
                "from src.constants import CONST\n"
            )
            f.flush()
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath, fix=True)
            assert result is not None
            assert result.has_changes is True
            assert len(result.changes) == 2
            content = filepath.read_text()
            assert "from src.infra.utils import helper" in content
            assert "from src.config.constants import CONST" in content
        finally:
            filepath.unlink()

    def test_exclude_patterns_filter(self):
        """Test that excluded files return None."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="test_"
        ) as f:
            f.write("from src.utils import something\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath, exclude_patterns=["test_*"])
            assert result is None
        finally:
            filepath.unlink()

    def test_unicode_decode_error_returns_none(self):
        """Test that binary files are skipped."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".py", delete=False
        ) as f:
            f.write(b"\xff\xfe")  # Invalid UTF-8
            filepath = Path(f.name)

        try:
            result = migrate_file(filepath)
            assert result is None
        finally:
            filepath.unlink()


class TestGenerateDiff:
    """Tests for the generate_diff function."""

    def test_diff_shows_changes(self):
        """Test that diff correctly shows import changes."""
        result = MigrationResult(
            filepath=Path("test.py"),
            changes=[(r"from src\.utils import", "from src.infra.utils import")],
            original_content="from src.utils import helper\n",
            new_content="from src.infra.utils import helper\n",
        )

        diff = generate_diff(result)
        assert "-from src.utils import helper" in diff
        assert "+from src.infra.utils import helper" in diff

    def test_empty_diff_for_no_changes(self):
        """Test that no diff is generated when content is the same."""
        result = MigrationResult(
            filepath=Path("test.py"),
            changes=[],
            original_content="from src.config.constants import FOO\n",
            new_content="from src.config.constants import FOO\n",
        )

        diff = generate_diff(result)
        assert diff == ""


class TestCollectFiles:
    """Tests for the collect_files function."""

    def test_collect_single_file(self):
        """Test collecting a single file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("# test\n")
            filepath = Path(f.name)

        try:
            files = collect_files(filepath)
            assert len(files) == 1
            assert files[0] == filepath
        finally:
            filepath.unlink()

    def test_collect_files_from_directory(self):
        """Test collecting Python files from a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.py").write_text("# file1\n")
            (tmppath / "file2.py").write_text("# file2\n")
            (tmppath / "readme.txt").write_text("readme\n")

            files = collect_files(tmppath)
            assert len(files) == 2
            assert all(f.suffix == ".py" for f in files)

    def test_collect_excludes_pycache(self):
        """Test that __pycache__ directories are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.py").write_text("# file\n")
            pycache = tmppath / "__pycache__"
            pycache.mkdir()
            (pycache / "cached.py").write_text("# cached\n")

            files = collect_files(tmppath)
            assert len(files) == 1
            assert "__pycache__" not in str(files[0])

    def test_collect_with_exclude_patterns(self):
        """Test collecting files with exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("# main\n")
            (tmppath / "test_main.py").write_text("# test\n")

            files = collect_files(tmppath, exclude_patterns=["test_*.py"])
            assert len(files) == 1
            assert files[0].name == "main.py"


class TestMain:
    """Tests for the main function."""

    def test_check_mode_no_changes(self, capsys):
        """Test check mode with no deprecated imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text(
                "from src.config.constants import FOO\n"
            )

            exit_code = main(["--check", "--path", str(tmppath)])

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "No deprecated imports found" in captured.out

    def test_check_mode_with_changes(self, capsys):
        """Test check mode with deprecated imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")

            exit_code = main(["--check", "--path", str(tmppath)])

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "would be modified" in captured.out
            # File should not be changed
            assert (
                (tmppath / "main.py").read_text()
                == "from src.utils import helper\n"
            )

    def test_fix_mode_applies_changes(self, capsys):
        """Test fix mode applies changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")

            exit_code = main(["--fix", "--path", str(tmppath)])

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Fixed" in captured.out
            # File should be updated
            content = (tmppath / "main.py").read_text()
            assert "from src.infra.utils import helper" in content

    def test_exclude_option(self, capsys):
        """Test exclude option filters files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")
            (tmppath / "test_main.py").write_text(
                "from src.utils import helper\n"
            )

            exit_code = main(
                ["--check", "--path", str(tmppath), "--exclude", "test_*.py"]
            )

            assert exit_code == 0
            captured = capsys.readouterr()
            # Should only find main.py, not test_main.py
            assert "1 file(s) would be modified" in captured.out

    def test_show_diff_option(self, capsys):
        """Test show-diff option outputs unified diff."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")

            exit_code = main(
                ["--check", "--path", str(tmppath), "--show-diff"]
            )

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "-from src.utils import helper" in captured.out
            assert "+from src.infra.utils import helper" in captured.out

    def test_default_to_check_mode(self, capsys):
        """Test that default mode is check (dry-run)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")

            exit_code = main(["--path", str(tmppath)])

            assert exit_code == 0
            # File should not be changed
            assert (
                (tmppath / "main.py").read_text()
                == "from src.utils import helper\n"
            )


class TestMigrationResult:
    """Tests for the MigrationResult class."""

    def test_has_changes_true(self):
        """Test has_changes returns True when there are changes."""
        result = MigrationResult(
            filepath=Path("test.py"),
            changes=[(r"from src\.utils import", "from src.infra.utils import")],
            original_content="from src.utils import foo\n",
            new_content="from src.infra.utils import foo\n",
        )
        assert result.has_changes is True

    def test_has_changes_false(self):
        """Test has_changes returns False when there are no changes."""
        result = MigrationResult(
            filepath=Path("test.py"),
            changes=[],
            original_content="from src.config.constants import FOO\n",
            new_content="from src.config.constants import FOO\n",
        )
        assert result.has_changes is False


class TestImportMappings:
    """Tests for import mappings coverage."""

    def test_all_mappings_have_valid_regex(self):
        """Test that all import mappings have valid regex patterns."""
        import re

        # Collect all patterns and validate them
        patterns_to_check = list(IMPORT_MAPPINGS.keys())

        def validate_pattern(pattern: str) -> str | None:
            """Return error message if pattern is invalid, None otherwise."""
            try:
                re.compile(pattern)
                return None
            except re.error as e:
                return f"'{pattern}': {e}"

        errors = list(filter(None, map(validate_pattern, patterns_to_check)))
        if errors:
            pytest.fail(f"Invalid regex patterns: {', '.join(errors)}")

    def test_mappings_cover_expected_modules(self):
        """Test that mappings cover the expected deprecated modules."""
        expected_modules = [
            "utils",
            "logging_setup",
            "constants",
            "exceptions",
            "models",
            "neo4j_utils",
            "worker",
            "data_loader",
            "qa_rag_system",
            "caching_layer",
            "graph_enhanced_router",
        ]

        for module in expected_modules:
            found = any(module in pattern for pattern in IMPORT_MAPPINGS)
            assert found, f"Missing mapping for module: {module}"
