"""Tests for src/core/type_aliases.py to improve coverage."""


class TestTypeAliases:
    """Test type aliases are properly defined and importable."""

    def test_json_dict_import(self) -> None:
        """Test JsonDict type alias."""
        from src.core.type_aliases import JsonDict

        # Type alias should work for dict with string keys
        data: JsonDict = {"key": "value", "number": 123}
        assert isinstance(data, dict)

    def test_json_list_import(self) -> None:
        """Test JsonList type alias."""
        from src.core.type_aliases import JsonList

        data: JsonList = [1, "two", {"three": 3}]
        assert isinstance(data, list)

    def test_string_list_import(self) -> None:
        """Test StringList type alias."""
        from src.core.type_aliases import StringList

        data: StringList = ["a", "b", "c"]
        assert isinstance(data, list)
        assert all(isinstance(s, str) for s in data)

    def test_string_dict_import(self) -> None:
        """Test StringDict type alias."""
        from src.core.type_aliases import StringDict

        data: StringDict = {"key": "value"}
        assert isinstance(data, dict)

    def test_int_list_import(self) -> None:
        """Test IntList type alias."""
        from src.core.type_aliases import IntList

        data: IntList = [1, 2, 3]
        assert isinstance(data, list)
        assert all(isinstance(i, int) for i in data)

    def test_nested_dict_import(self) -> None:
        """Test NestedDict type alias."""
        from src.core.type_aliases import NestedDict

        data: NestedDict = {"outer": {"inner": "value"}}
        assert isinstance(data, dict)
        assert isinstance(data["outer"], dict)

    def test_nested_list_import(self) -> None:
        """Test NestedList type alias."""
        from src.core.type_aliases import NestedList

        data: NestedList = [["a", "b"], ["c", "d"]]
        assert isinstance(data, list)
        assert all(isinstance(inner, list) for inner in data)

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from src.core import type_aliases

        assert "JsonDict" in type_aliases.__all__
        assert "JsonList" in type_aliases.__all__
        assert "StringList" in type_aliases.__all__
        assert "StringDict" in type_aliases.__all__
        assert "IntList" in type_aliases.__all__
        assert "NestedDict" in type_aliases.__all__
        assert "NestedList" in type_aliases.__all__
