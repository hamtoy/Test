"""Tests for graph_router module.

Covers:
- GraphEnhancedRouter initialization and routing
- _fetch_query_types() with exception handling
- _build_router_prompt() prompt building
- _log_routing() with exception handling
- Fallback selection logic
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from neo4j.exceptions import Neo4jError

from src.routing.graph_router import GraphEnhancedRouter, GraphRouter


class TestGraphEnhancedRouterInit:
    """Tests for GraphEnhancedRouter initialization."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default parameters."""
        with (
            patch("src.routing.graph_router.QAKnowledgeGraph") as mock_kg_cls,
            patch("src.routing.graph_router.GeminiModelClient") as mock_llm_cls,
        ):
            mock_kg = MagicMock()
            mock_llm = MagicMock()
            mock_kg_cls.return_value = mock_kg
            mock_llm_cls.return_value = mock_llm

            router = GraphEnhancedRouter()

            assert router.kg is mock_kg
            assert router.llm is mock_llm

    def test_init_with_provided_kg_and_llm(self) -> None:
        """Test initialization with provided kg and llm."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        assert router.kg is mock_kg
        assert router.llm is mock_llm

    def test_graph_router_alias(self) -> None:
        """Test GraphRouter is an alias for GraphEnhancedRouter."""
        assert GraphRouter is GraphEnhancedRouter


class TestFetchQueryTypes:
    """Tests for _fetch_query_types method."""

    def test_fetch_query_types_success(self) -> None:
        """Test successful query type fetch."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_session = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_graph.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.run.return_value = [
            {"name": "explanation", "korean": "설명", "limit": 5},
            {"name": "summary", "korean": "요약", "limit": 3},
        ]

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        result = router._fetch_query_types()

        assert len(result) == 2
        assert result[0]["name"] == "explanation"
        assert result[1]["name"] == "summary"

    def test_fetch_query_types_no_graph(self) -> None:
        """Test fetch returns empty list when no graph available."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_kg._graph = None

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        result = router._fetch_query_types()

        assert result == []

    def test_fetch_query_types_neo4j_error(self) -> None:
        """Test fetch handles Neo4jError gracefully."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(
            side_effect=Neo4jError("Connection failed")
        )

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        result = router._fetch_query_types()

        assert result == []

    def test_fetch_query_types_unknown_exception(self) -> None:
        """Test fetch handles unknown exceptions gracefully."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        result = router._fetch_query_types()

        assert result == []


class TestBuildRouterPrompt:
    """Tests for _build_router_prompt method."""

    def test_build_router_prompt_with_qtypes(self) -> None:
        """Test prompt building with query types."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        qtypes = [
            {"name": "explanation", "korean": "설명", "limit": 5},
            {"name": "summary", "korean": "요약", "limit": 3},
        ]

        prompt = router._build_router_prompt("테스트 입력", qtypes)

        assert "테스트 입력" in prompt
        assert "explanation (설명)" in prompt
        assert "summary (요약)" in prompt
        assert "limit: 5" in prompt
        assert "limit: 3" in prompt

    def test_build_router_prompt_empty_qtypes(self) -> None:
        """Test prompt building with empty query types."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        prompt = router._build_router_prompt("테스트 입력", [])

        assert "테스트 입력" in prompt
        assert "(등록된 QueryType 없음)" in prompt

    def test_build_router_prompt_missing_fields(self) -> None:
        """Test prompt building with missing fields in qtypes."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        qtypes = [
            {"name": "test"},  # Missing korean and limit
            {},  # All fields missing
        ]

        prompt = router._build_router_prompt("입력", qtypes)

        assert "test ()" in prompt
        assert " ()" in prompt


class TestLogRouting:
    """Tests for _log_routing method."""

    def test_log_routing_success(self) -> None:
        """Test successful routing log."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_session = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_graph.session.return_value.__exit__ = MagicMock(return_value=False)

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        router._log_routing("test input", "explanation")

        mock_session.run.assert_called_once()

    def test_log_routing_no_graph(self) -> None:
        """Test log routing when no graph available."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_kg._graph = None

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        # Should not raise
        router._log_routing("test input", "explanation")

    def test_log_routing_neo4j_error(self) -> None:
        """Test log routing handles Neo4jError gracefully."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(
            side_effect=Neo4jError("Write failed")
        )

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        # Should not raise
        router._log_routing("test input", "explanation")

    def test_log_routing_unknown_exception(self) -> None:
        """Test log routing handles unknown exceptions gracefully."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)
        # Should not raise
        router._log_routing("test input", "explanation")


class TestRouteAndGenerate:
    """Tests for route_and_generate method."""

    def test_route_and_generate_matches_handler(self) -> None:
        """Test routing matches correct handler."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_kg._graph = None

        mock_llm.generate.return_value = "explanation"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handler_called = []
        handlers = {
            "explanation": lambda x: handler_called.append(("explanation", x)),
            "summary": lambda x: handler_called.append(("summary", x)),
        }

        result = router.route_and_generate("테스트 입력", handlers)

        assert result["choice"] == "explanation"
        assert ("explanation", "테스트 입력") in handler_called

    def test_route_and_generate_fallback_to_explanation(self) -> None:
        """Test fallback to 'explanation' when no match found."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_session = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_graph.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [
            {"name": "explanation", "korean": "설명", "limit": 5}
        ]

        mock_llm.generate.return_value = "unknown_type"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handlers = {
            "explanation": lambda x: "explanation_result",
        }

        result = router.route_and_generate("테스트", handlers)

        assert result["choice"] == "explanation"

    def test_route_and_generate_fallback_to_first_qtype(self) -> None:
        """Test fallback to first query type when explanation not available."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_session = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_graph.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [
            {"name": "summary", "korean": "요약", "limit": 3}
        ]

        mock_llm.generate.return_value = "unknown_type"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handlers = {
            "summary": lambda x: "summary_result",
        }

        result = router.route_and_generate("테스트", handlers)

        assert result["choice"] == "summary"

    def test_route_and_generate_no_qtypes_fallback(self) -> None:
        """Test fallback to 'explanation' when no query types available."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_kg._graph = None

        mock_llm.generate.return_value = "anything"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handlers = {}

        result = router.route_and_generate("테스트", handlers)

        assert result["choice"] == "explanation"
        assert result["output"] is None

    def test_route_and_generate_handler_not_found(self) -> None:
        """Test when chosen handler is not in handlers dict."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_kg._graph = None

        mock_llm.generate.return_value = "explanation"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handlers = {
            "summary": lambda x: "summary_result",
        }

        result = router.route_and_generate("테스트", handlers)

        assert result["choice"] == "explanation"
        assert result["output"] is None

    def test_route_and_generate_partial_match(self) -> None:
        """Test routing with partial match in LLM response."""
        mock_kg = MagicMock()
        mock_llm = MagicMock()
        mock_session = MagicMock()
        mock_graph = MagicMock()

        mock_kg._graph = mock_graph
        mock_graph.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_graph.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [
            {"name": "summary", "korean": "요약", "limit": 3},
            {"name": "explanation", "korean": "설명", "limit": 5},
        ]

        # LLM responds with text containing the type name
        mock_llm.generate.return_value = "I think summary is best"

        router = GraphEnhancedRouter(kg=mock_kg, llm=mock_llm)

        handlers = {
            "summary": lambda x: "summary_result",
        }

        result = router.route_and_generate("테스트", handlers)

        assert result["choice"] == "summary"
        assert result["output"] == "summary_result"
