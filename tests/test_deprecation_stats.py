"""Tests for the deprecation_stats.py script."""

import json
import tempfile
from pathlib import Path

from scripts.deprecation_stats import (
    analyze_file,
    analyze_usage,
    generate_report,
    generate_summary_text,
    get_trend_indicator,
    main,
    save_stats_json,
)


class TestAnalyzeFile:
    """Tests for the analyze_file function."""

    def test_no_deprecations(self):
        """Test file with no deprecated imports."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from src.config.constants import FOO\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = analyze_file(filepath)
            assert result == {}
        finally:
            filepath.unlink()

    def test_single_deprecation(self):
        """Test file with a single deprecated import."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from src.utils import helper\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = analyze_file(filepath)
            assert "src.utils" in result
            assert result["src.utils"] == 1
        finally:
            filepath.unlink()

    def test_multiple_deprecations_same_module(self):
        """Test file with multiple deprecated imports from same module."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from src.utils import helper\nfrom src.utils import another\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = analyze_file(filepath)
            assert "src.utils" in result
            assert result["src.utils"] == 2
        finally:
            filepath.unlink()

    def test_multiple_deprecations_different_modules(self):
        """Test file with deprecated imports from different modules."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("from src.utils import helper\nfrom src.constants import CONST\n")
            f.flush()
            filepath = Path(f.name)

        try:
            result = analyze_file(filepath)
            assert "src.utils" in result
            assert "src.constants" in result
        finally:
            filepath.unlink()


class TestAnalyzeUsage:
    """Tests for the analyze_usage function."""

    def test_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = analyze_usage(Path(tmpdir))
            assert stats["total_calls"] == 0
            assert stats["unique_callers"] == 0
            assert stats["by_module"] == {}

    def test_directory_with_deprecations(self):
        """Test analyzing a directory with deprecated imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.py").write_text("from src.utils import helper\n")
            (tmppath / "file2.py").write_text("from src.constants import CONST\n")

            stats = analyze_usage(tmppath)
            assert stats["total_calls"] == 2
            assert stats["unique_callers"] == 2
            assert len(stats["files_with_deprecations"]) == 2

    def test_exclude_patterns(self):
        """Test that exclude patterns work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("from src.utils import helper\n")
            (tmppath / "test_main.py").write_text("from src.utils import helper\n")

            stats = analyze_usage(tmppath, exclude_patterns=["test_"])
            assert stats["total_calls"] == 1
            assert stats["unique_callers"] == 1


class TestGenerateSummaryText:
    """Tests for the generate_summary_text function."""

    def test_summary_with_data(self):
        """Test generating summary with usage data."""
        stats = {
            "total_calls": 10,
            "unique_callers": 5,
            "by_module": {"src.utils": 6, "src.constants": 4},
            "files_with_deprecations": ["file1.py", "file2.py"],
        }

        summary = generate_summary_text(stats)  # type: ignore[arg-type]
        assert "Total deprecated calls: 10" in summary
        assert "Unique callers: 5" in summary
        assert "src.utils: 6 call(s)" in summary

    def test_summary_empty(self):
        """Test generating summary with no data."""
        stats = {
            "total_calls": 0,
            "unique_callers": 0,
            "by_module": {},
            "files_with_deprecations": [],
        }

        summary = generate_summary_text(stats)  # type: ignore[arg-type]
        assert "Total deprecated calls: 0" in summary


class TestGenerateReport:
    """Tests for the generate_report function."""

    def test_html_report_content(self):
        """Test that HTML report contains expected content."""
        stats = {
            "total_calls": 15,
            "unique_callers": 3,
            "by_module": {"src.utils": 10, "src.constants": 5},
            "files_with_deprecations": ["src/main.py", "src/helper.py"],
        }

        html = generate_report(stats)  # type: ignore[arg-type]
        assert "<!DOCTYPE html>" in html
        assert "15" in html  # total calls
        assert "3" in html  # unique callers
        assert "src.utils" in html
        assert "src.constants" in html

    def test_html_report_file_output(self):
        """Test that HTML report is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            stats = {
                "total_calls": 5,
                "unique_callers": 2,
                "by_module": {"src.utils": 5},
                "files_with_deprecations": ["file.py"],
            }

            generate_report(stats, output_path)  # type: ignore[arg-type]

            assert output_path.exists()
            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content


class TestGetTrendIndicator:
    """Tests for the get_trend_indicator function."""

    def test_decreasing_trend(self):
        """Test decreasing trend indicator."""
        assert "DECREASING" in get_trend_indicator(5, 10)

    def test_increasing_trend(self):
        """Test increasing trend indicator."""
        assert "INCREASING" in get_trend_indicator(10, 5)

    def test_stable_trend(self):
        """Test stable trend indicator."""
        assert "STABLE" in get_trend_indicator(5, 5)

    def test_new_from_zero(self):
        """Test new indicator when previous was zero."""
        assert "NEW" in get_trend_indicator(5, 0)


class TestSaveStatsJson:
    """Tests for the save_stats_json function."""

    def test_json_output(self):
        """Test that JSON output contains expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "stats.json"
            stats = {
                "total_calls": 10,
                "unique_callers": 3,
                "by_module": {"src.utils": 10},
                "files_with_deprecations": ["file.py"],
            }

            save_stats_json(stats, output_path)  # type: ignore[arg-type]

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert "timestamp" in data
            assert "stats" in data
            assert data["stats"]["total_calls"] == 10


class TestMain:
    """Tests for the main function."""

    def test_main_basic(self, capsys):
        """Test basic main execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.py").write_text("from src.utils import helper\n")

            exit_code = main(["--path", str(tmppath)])

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Total deprecated calls: 1" in captured.out

    def test_main_html_output(self, capsys):
        """Test main with HTML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.py").write_text("from src.utils import helper\n")
            html_path = tmppath / "report.html"

            exit_code = main(["--path", str(tmppath), "--html", str(html_path)])

            assert exit_code == 0
            assert html_path.exists()

    def test_main_quiet_mode(self, capsys):
        """Test main with quiet mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.py").write_text("from src.utils import helper\n")

            exit_code = main(["--path", str(tmppath), "--quiet"])

            assert exit_code == 0
            captured = capsys.readouterr()
            # Summary should not be printed
            assert "Total deprecated calls" not in captured.out

    def test_main_nonexistent_path(self, capsys):
        """Test main with nonexistent path."""
        exit_code = main(["--path", "/nonexistent/path"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err
