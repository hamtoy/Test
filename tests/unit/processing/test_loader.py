"""Tests for processing loader module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.processing.loader import load_examples_from_file, parse_yaml_examples


class TestLoadExamplesFromFile:
    """Test load_examples_from_file function."""

    @patch("builtins.open", new_callable=mock_open, read_data="key: value\n")
    @patch("src.processing.loader.parse_yaml_examples")
    def test_load_examples_from_file_success(
        self, mock_parse: Mock, mock_file: Mock
    ) -> None:
        """Test successful file loading."""
        mock_parse.return_value = [{"key": "value"}]
        
        result = load_examples_from_file(Path("/tmp/test.yaml"))
        
        assert result == [{"key": "value"}]
        mock_parse.assert_called_once()

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_examples_from_file_not_found(self, mock_file: Mock) -> None:
        """Test handling of missing file."""
        result = load_examples_from_file(Path("/tmp/nonexistent.yaml"))
        
        assert result == []

    @patch("builtins.open", side_effect=PermissionError())
    def test_load_examples_from_file_permission_error(self, mock_file: Mock) -> None:
        """Test handling of permission error."""
        result = load_examples_from_file(Path("/tmp/noperm.yaml"))
        
        assert result == []


class TestParseYamlExamples:
    """Test parse_yaml_examples function."""

    def test_parse_yaml_examples_valid_yaml(self) -> None:
        """Test parsing valid YAML."""
        yaml_content = "examples:\n  - query: test\n    answer: result\n"
        
        result = parse_yaml_examples(yaml_content)
        
        assert len(result) == 1
        assert result[0]["query"] == "test"
        assert result[0]["answer"] == "result"

    def test_parse_yaml_examples_empty_string(self) -> None:
        """Test parsing empty string."""
        result = parse_yaml_examples("")
        
        assert result == []

    def test_parse_yaml_examples_invalid_yaml(self) -> None:
        """Test parsing invalid YAML."""
        yaml_content = "invalid: yaml: content: :"
        
        result = parse_yaml_examples(yaml_content)
        
        assert result == []
