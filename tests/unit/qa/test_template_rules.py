"""Tests for Neo4j template rules functionality."""
# mypy: ignore-errors

from unittest.mock import MagicMock, patch


from src.qa.template_rules import (
    get_all_template_context,
    get_best_practices,
    get_common_mistakes,
    get_constraint_details,
    get_neo4j_config,
    get_rules_for_query_type,
    get_rules_from_neo4j,
)


class TestGetRulesForQueryType:
    """Tests for get_rules_for_query_type function."""

    @patch("neo4j.GraphDatabase")
    def test_get_rules_success(self, mock_graph_db):
        """Test successful rule retrieval."""
        # Mock setup
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {
                "title": "Rule 1",
                "content": "Content 1",
                "category": "Category A",
                "subcategory": "Subcategory 1",
            }
        ]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        # Clear cache first
        get_rules_for_query_type.cache_clear()

        # Execute
        result = get_rules_for_query_type(
            "explanation", "neo4j://localhost", "user", "password"
        )

        # Verify
        assert len(result) == 1
        assert result[0]["title"] == "Rule 1"
        mock_driver.close.assert_called_once()

    @patch("neo4j.GraphDatabase")
    def test_get_rules_empty_result(self, mock_graph_db):
        """Test handling of empty results."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_rules_for_query_type.cache_clear()

        result = get_rules_for_query_type(
            "unknown_type", "neo4j://localhost", "user", "password"
        )

        assert result == []

    @patch("neo4j.GraphDatabase")
    def test_caching_works(self, mock_graph_db):
        """Test LRU cache functionality."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_rules_for_query_type.cache_clear()

        # First call
        get_rules_for_query_type("test", "uri", "user", "pass")
        first_call_count = mock_graph_db.driver.call_count

        # Second call with same arguments (should use cache)
        get_rules_for_query_type("test", "uri", "user", "pass")
        second_call_count = mock_graph_db.driver.call_count

        # Cache should prevent additional driver calls
        assert first_call_count == second_call_count

    @patch("neo4j.GraphDatabase")
    def test_multiple_rules_returned(self, mock_graph_db):
        """Test multiple rules are properly returned."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {
                "title": "Rule 1",
                "content": "Content 1",
                "category": "Cat A",
                "subcategory": "Sub A",
            },
            {
                "title": "Rule 2",
                "content": "Content 2",
                "category": "Cat B",
                "subcategory": "Sub B",
            },
        ]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_rules_for_query_type.cache_clear()

        result = get_rules_for_query_type("test", "uri", "user", "pass")

        assert len(result) == 2
        assert result[0]["title"] == "Rule 1"
        assert result[1]["title"] == "Rule 2"


class TestGetRulesFromNeo4j:
    """Tests for get_rules_from_neo4j function."""

    @patch("neo4j.GraphDatabase")
    def test_get_rules_from_neo4j_success(self, mock_graph_db):
        """Test successful Neo4j rule retrieval."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_records = [
            {"name": "rule1", "text": "text1", "category": "cat1", "priority": 1}
        ]

        mock_session.__enter__.return_value.run.return_value = mock_records
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_rules_from_neo4j.cache_clear()

        result = get_rules_from_neo4j("test_type", "uri", "user", "pass")

        assert len(result) == 1
        assert result[0]["name"] == "rule1"
        mock_driver.close.assert_called_once()


class TestGetCommonMistakes:
    """Tests for get_common_mistakes function."""

    @patch("neo4j.GraphDatabase")
    def test_with_category_filter(self, mock_graph_db):
        """Test with category filtering."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {"title": "Mistake 1", "preview": "Preview text", "subcategory": "질의"}
        ]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_common_mistakes.cache_clear()

        result = get_common_mistakes("질의", "neo4j://localhost", "user", "password")

        assert len(result) == 1
        assert result[0]["subcategory"] == "질의"

    @patch("neo4j.GraphDatabase")
    def test_without_category_filter(self, mock_graph_db):
        """Test without category filtering."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {"title": "M1", "preview": "P1", "subcategory": "질의"},
            {"title": "M2", "preview": "P2", "subcategory": "답변"},
        ]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_common_mistakes.cache_clear()

        result = get_common_mistakes(None, "neo4j://localhost", "user", "password")

        assert len(result) == 2


class TestGetBestPractices:
    """Tests for get_best_practices function."""

    @patch("neo4j.GraphDatabase")
    def test_get_best_practices_success(self, mock_graph_db):
        """Test successful best practices retrieval."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [{"title": "BP1", "preview": "Preview1"}]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_best_practices.cache_clear()

        result = get_best_practices("uri", "user", "pass")

        assert len(result) == 1
        assert "BP1" in result[0]
        assert "Preview1" in result[0]


class TestGetConstraintDetails:
    """Tests for get_constraint_details function."""

    @patch("neo4j.GraphDatabase")
    def test_get_constraint_details_success(self, mock_graph_db):
        """Test successful constraint details retrieval."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [{"title": "Constraint1", "preview": "Preview1"}]

        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        get_constraint_details.cache_clear()

        result = get_constraint_details("test_type", "uri", "user", "pass")

        assert len(result) == 1
        assert "Constraint1" in result[0]


class TestGetAllTemplateContext:
    """Tests for get_all_template_context function."""

    @patch("src.qa.template_rules.get_rules_for_query_type")
    @patch("src.qa.template_rules.get_common_mistakes")
    @patch("src.qa.template_rules.get_best_practices")
    @patch("src.qa.template_rules.get_constraint_details")
    @patch("src.qa.template_rules.get_rules_from_neo4j")
    def test_full_context_answer_stage(
        self,
        mock_rules_neo4j,
        mock_constraints,
        mock_best,
        mock_mistakes,
        mock_rules,
    ):
        """Test full context generation for answer stage."""
        mock_rules.return_value = [{"rule": "test"}]
        mock_mistakes.return_value = [{"mistake": "test"}]
        mock_best.return_value = ["best practice"]
        mock_constraints.return_value = ["constraint"]
        mock_rules_neo4j.return_value = [{"neo4j_rule": "test"}]

        context = get_all_template_context(
            query_type="explanation",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass",
            include_mistakes=True,
            include_best_practices=True,
            include_constraints=True,
            context_stage="answer",
        )

        assert "guide_rules" in context
        assert "common_mistakes" in context
        assert "best_practices" in context
        assert "constraint_details" in context
        assert "rules" in context

    @patch("src.qa.template_rules.get_rules_for_query_type")
    @patch("src.qa.template_rules.get_rules_from_neo4j")
    def test_minimal_context(self, mock_rules_neo4j, mock_rules):
        """Test minimal context generation."""
        mock_rules.return_value = []
        mock_rules_neo4j.return_value = []

        context = get_all_template_context(
            query_type="test",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass",
            include_mistakes=False,
            include_best_practices=False,
            include_constraints=False,
        )

        assert "guide_rules" in context
        assert "common_mistakes" not in context
        assert "best_practices" not in context
        assert "constraint_details" not in context

    @patch("src.qa.template_rules.get_rules_for_query_type")
    @patch("src.qa.template_rules.get_common_mistakes")
    @patch("src.qa.template_rules.get_rules_from_neo4j")
    def test_rules_error_handling(self, mock_rules_neo4j, mock_mistakes, mock_rules):
        """Test error handling when rules retrieval fails."""
        mock_rules.return_value = []
        mock_mistakes.return_value = []
        mock_rules_neo4j.side_effect = Exception("Connection failed")

        # Should not raise exception, but return empty rules list
        context = get_all_template_context(
            query_type="test",
            neo4j_uri="neo4j://localhost",
            neo4j_user="user",
            neo4j_password="pass",
        )

        assert context["rules"] == []

    @patch("src.qa.template_rules.get_rules_for_query_type")
    @patch("src.qa.template_rules.get_common_mistakes")
    @patch("src.qa.template_rules.get_rules_from_neo4j")
    def test_query_stage_context(self, mock_rules_neo4j, mock_mistakes, mock_rules):
        """Test context generation for query stage."""
        mock_rules.return_value = []
        mock_mistakes.return_value = []
        mock_rules_neo4j.return_value = []

        get_all_template_context(
            query_type="explanation",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass",
            include_mistakes=True,
            context_stage="query",
        )

        # In query stage, mistakes should be from "질의" category
        mock_mistakes.assert_called_once()
        call_args = mock_mistakes.call_args
        assert call_args[0][0] == "질의"


class TestGetNeo4jConfig:
    """Tests for get_neo4j_config function."""

    @patch.dict(
        "os.environ",
        {
            "NEO4J_URI": "neo4j://custom",
            "NEO4J_USERNAME": "admin",
            "NEO4J_PASSWORD": "secret",
        },
    )
    def test_from_env_with_username(self):
        """Test config from environment with NEO4J_USERNAME."""
        config = get_neo4j_config()

        assert config["neo4j_uri"] == "neo4j://custom"
        assert config["neo4j_user"] == "admin"
        assert config["neo4j_password"] == "secret"

    @patch.dict(
        "os.environ",
        {"NEO4J_USER": "user_legacy", "NEO4J_PASSWORD": "pass123"},
        clear=True,
    )
    def test_fallback_to_neo4j_user(self):
        """Test fallback to NEO4J_USER when USERNAME not set."""
        config = get_neo4j_config()

        assert config["neo4j_user"] == "user_legacy"

    @patch.dict("os.environ", {}, clear=True)
    def test_default_values(self):
        """Test default configuration values."""
        config = get_neo4j_config()

        assert "neo4j_uri" in config
        assert config["neo4j_user"] == "neo4j"  # Default value
        assert config["neo4j_password"] == ""  # Default value
